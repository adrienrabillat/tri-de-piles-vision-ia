"""
inference_server.py
Serveur FastAPI pour l'inference en temps reel et l'orchestration du pipeline.

Endpoints :
  - POST /predict          : Detection sur une image uploadee
  - POST /predict/webcam   : Detection sur un frame base64
  - GET  /config           : Configuration actuelle
  - POST /config           : Modifier la configuration
  - POST /generate         : Lancer la generation de dataset (async)
  - POST /train            : Lancer l'entrainement YOLO (async)
  - GET  /status           : Statut des jobs en cours
  - GET  /metrics          : Metriques du dernier entrainement
  - GET  /dataset/stats    : Statistiques du dataset
  - WS   /ws/training      : WebSocket pour le suivi du training en temps reel

Execution :
    pip install fastapi uvicorn python-multipart pillow ultralytics onnxruntime
    cd backend && uvicorn inference_server:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import json
import time
import asyncio
import base64
import io
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# Ajouter le dossier parent au path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import numpy as np
from PIL import Image

# ==========================================================
# APP FASTAPI
# ==========================================================

app = FastAPI(
    title="Battery Sorting API",
    description="API d'inference et d'orchestration pour le centre de tri de piles",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# ETAT GLOBAL
# ==========================================================

class AppState:
    def __init__(self):
        self.model = None
        self.model_type = None  # "onnx" ou "ultralytics"
        self.jobs: Dict[str, Dict] = {}
        self.training_ws_clients: List[WebSocket] = []
        self.config = self._load_config()

    def _load_config(self):
        """Charge la config depuis config.py"""
        try:
            import config as cfg
            return {
                "num_images": cfg.NUM_IMAGES,
                "render_engine": cfg.RENDER_ENGINE,
                "render_width": cfg.RENDER_WIDTH,
                "render_height": cfg.RENDER_HEIGHT,
                "random_seed": cfg.RANDOM_SEED,
                "battery_count_range": list(cfg.BATTERY_RANDOM["count_range"]),
                "battery_types": cfg.BATTERY_RANDOM["types"],
                "confidence_threshold": getattr(cfg, "CONFIDENCE_THRESHOLD", 0.25),
                "iou_threshold": getattr(cfg, "IOU_THRESHOLD", 0.45),
                "distractors_enabled": getattr(cfg, "DISTRACTORS", {}).get("enabled", False),
                "mixed_rendering_enabled": getattr(cfg, "MIXED_RENDERING", {}).get("enabled", False),
                "camera_artifacts_enabled": True,
                "advanced_textures_enabled": True,
            }
        except Exception:
            return {
                "num_images": 100,
                "render_engine": "BLENDER_EEVEE",
                "confidence_threshold": 0.25,
                "iou_threshold": 0.45,
            }

    def load_model(self):
        """Charge le modele d'inference (ONNX ou Ultralytics)."""
        if self.model is not None:
            return

        import config as cfg

        # Essayer ONNX d'abord
        onnx_path = getattr(cfg, "ONNX_MODEL_PATH", "")
        if os.path.exists(onnx_path):
            try:
                import onnxruntime as ort
                self.model = ort.InferenceSession(onnx_path)
                self.model_type = "onnx"
                print(f"[OK] Modele ONNX charge: {onnx_path}")
                return
            except Exception as e:
                print(f"[WARN] ONNX echoue: {e}")

        # Fallback Ultralytics
        pt_path = getattr(cfg, "PT_MODEL_PATH", "")
        if os.path.exists(pt_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(pt_path)
                self.model_type = "ultralytics"
                print(f"[OK] Modele Ultralytics charge: {pt_path}")
                return
            except Exception as e:
                print(f"[WARN] Ultralytics echoue: {e}")

        # Chercher n'importe quel .pt dans runs/
        runs_dir = os.path.join(PROJECT_DIR, "runs", "detect")
        if os.path.exists(runs_dir):
            for root, dirs, files in os.walk(runs_dir):
                for f in files:
                    if f == "best.pt":
                        try:
                            from ultralytics import YOLO
                            path = os.path.join(root, f)
                            self.model = YOLO(path)
                            self.model_type = "ultralytics"
                            print(f"[OK] Modele trouve et charge: {path}")
                            return
                        except Exception:
                            continue

        print("[WARN] Aucun modele trouve. L'inference ne sera pas disponible.")


state = AppState()


# ==========================================================
# MODELES PYDANTIC
# ==========================================================

class PredictionResult(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: Dict[str, float]  # x1, y1, x2, y2

class PredictionResponse(BaseModel):
    predictions: List[PredictionResult]
    inference_time_ms: float
    image_size: Dict[str, int]

class ConfigUpdate(BaseModel):
    num_images: Optional[int] = None
    render_engine: Optional[str] = None
    random_seed: Optional[int] = None
    confidence_threshold: Optional[float] = None
    iou_threshold: Optional[float] = None
    distractors_enabled: Optional[bool] = None
    mixed_rendering_enabled: Optional[bool] = None
    camera_artifacts_enabled: Optional[bool] = None
    advanced_textures_enabled: Optional[bool] = None
    battery_count_range: Optional[List[int]] = None

class GenerateRequest(BaseModel):
    num_images: int = 100
    seed: int = 42
    use_v3: bool = True

class TrainRequest(BaseModel):
    model: str = "yolov8n.pt"
    epochs: int = 50
    batch: int = 16
    imgsz: int = 640
    name: str = "battery_sorting"


# ==========================================================
# FONCTIONS UTILITAIRES
# ==========================================================

CLASS_NAMES = ["AA", "AAA", "button", "9V", "C", "D"]

def preprocess_image(image: Image.Image, target_size: int = 640):
    """Preprocesse une image pour l'inference."""
    img = image.convert("RGB")
    original_size = img.size

    # Redimensionner en gardant le ratio
    ratio = target_size / max(original_size)
    new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
    img = img.resize(new_size, Image.BILINEAR)

    # Padding pour atteindre target_size x target_size
    padded = Image.new("RGB", (target_size, target_size), (114, 114, 114))
    offset = ((target_size - new_size[0]) // 2, (target_size - new_size[1]) // 2)
    padded.paste(img, offset)

    # Convertir en numpy array normalise
    arr = np.array(padded).astype(np.float32) / 255.0
    arr = np.transpose(arr, (2, 0, 1))  # HWC -> CHW
    arr = np.expand_dims(arr, 0)  # Batch dimension

    return arr, original_size, ratio, offset


def run_inference_ultralytics(image: Image.Image, conf: float, iou: float):
    """Inference avec le modele Ultralytics."""
    results = state.model(image, conf=conf, iou=iou, verbose=False)
    predictions = []

    for r in results:
        boxes = r.boxes
        if boxes is None:
            continue
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            conf_val = float(boxes.conf[i].item())
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            predictions.append(PredictionResult(
                class_id=cls_id,
                class_name=CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"class_{cls_id}",
                confidence=round(conf_val, 4),
                bbox={"x1": round(x1, 1), "y1": round(y1, 1),
                      "x2": round(x2, 1), "y2": round(y2, 1)},
            ))
    return predictions


# ==========================================================
# ENDPOINTS
# ==========================================================

@app.on_event("startup")
async def startup():
    state.load_model()


@app.get("/")
async def root():
    return {
        "name": "Battery Sorting API",
        "version": "3.0.0",
        "model_loaded": state.model is not None,
        "model_type": state.model_type,
        "endpoints": [
            "POST /predict",
            "POST /predict/webcam",
            "GET /config",
            "POST /config",
            "POST /generate",
            "POST /train",
            "GET /status",
            "GET /metrics",
            "GET /dataset/stats",
        ],
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(file: UploadFile = File(...)):
    """Detection d'objets sur une image uploadee."""
    if state.model is None:
        raise HTTPException(status_code=503, detail="Aucun modele charge")

    contents = await file.read()
    image = Image.open(io.BytesIO(contents))

    start = time.time()
    conf = state.config.get("confidence_threshold", 0.25)
    iou = state.config.get("iou_threshold", 0.45)

    if state.model_type == "ultralytics":
        predictions = run_inference_ultralytics(image, conf, iou)
    else:
        raise HTTPException(status_code=501, detail="ONNX inference non implementee")

    inference_time = (time.time() - start) * 1000

    return PredictionResponse(
        predictions=predictions,
        inference_time_ms=round(inference_time, 2),
        image_size={"width": image.size[0], "height": image.size[1]},
    )


@app.post("/predict/webcam", response_model=PredictionResponse)
async def predict_webcam(data: Dict[str, str]):
    """Detection sur un frame webcam encode en base64."""
    if state.model is None:
        raise HTTPException(status_code=503, detail="Aucun modele charge")

    image_b64 = data.get("image", "")
    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]

    image_bytes = base64.b64decode(image_b64)
    image = Image.open(io.BytesIO(image_bytes))

    start = time.time()
    conf = state.config.get("confidence_threshold", 0.25)
    iou = state.config.get("iou_threshold", 0.45)

    if state.model_type == "ultralytics":
        predictions = run_inference_ultralytics(image, conf, iou)
    else:
        raise HTTPException(status_code=501, detail="ONNX inference non implementee")

    inference_time = (time.time() - start) * 1000

    return PredictionResponse(
        predictions=predictions,
        inference_time_ms=round(inference_time, 2),
        image_size={"width": image.size[0], "height": image.size[1]},
    )


@app.get("/config")
async def get_config():
    return state.config


@app.post("/config")
async def update_config(update: ConfigUpdate):
    """Met a jour la configuration."""
    updates = update.dict(exclude_none=True)
    state.config.update(updates)
    return {"status": "ok", "config": state.config}


@app.post("/generate")
async def generate_dataset(req: GenerateRequest):
    """Lance la generation de dataset en arriere-plan."""
    job_id = str(uuid.uuid4())[:8]

    state.jobs[job_id] = {
        "type": "generate",
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "params": req.dict(),
        "progress": 0,
    }

    async def run_generation():
        try:
            import subprocess
            import shutil
            
            blender_cmd = "blender"
            mac_blender = "/Applications/Blender.app/Contents/MacOS/Blender"
            if shutil.which("blender") is None and os.path.exists(mac_blender):
                blender_cmd = mac_blender
                
            script = "dataset_generator_v3.py" if req.use_v3 else "dataset_generator.py"
            cmd = [
                blender_cmd, "--background", "--python",
                os.path.join(PROJECT_DIR, script),
                "--", "--num_images", str(req.num_images),
                "--seed", str(req.seed),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=PROJECT_DIR,
            )

            output_lines = []
            async for line in proc.stdout:
                line_str = line.decode().strip()
                output_lines.append(line_str)
                # Parser le progres
                if "/" in line_str and "Generation" not in line_str:
                    try:
                        parts = line_str.split("[")[1].split("]")[0].split("/")
                        current = int(parts[0])
                        total = int(parts[1])
                        state.jobs[job_id]["progress"] = round(current / total * 100, 1)
                    except (IndexError, ValueError):
                        pass

            await proc.wait()
            state.jobs[job_id]["status"] = "completed" if proc.returncode == 0 else "failed"
            state.jobs[job_id]["completed_at"] = datetime.now().isoformat()
            state.jobs[job_id]["return_code"] = proc.returncode
            state.jobs[job_id]["progress"] = 100 if proc.returncode == 0 else state.jobs[job_id]["progress"]

        except Exception as e:
            state.jobs[job_id]["status"] = "failed"
            state.jobs[job_id]["error"] = str(e)

    asyncio.create_task(run_generation())
    return {"job_id": job_id, "status": "started"}


@app.post("/train")
async def train_model(req: TrainRequest):
    """Lance l'entrainement YOLO en arriere-plan."""
    job_id = str(uuid.uuid4())[:8]

    state.jobs[job_id] = {
        "type": "train",
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "params": req.dict(),
        "progress": 0,
        "metrics": {},
    }

    async def run_training():
        try:
            import subprocess
            # Lancer le split en premier pour garantir que yolo_dataset/data.yaml existe
            split_cmd = [sys.executable, os.path.join(PROJECT_DIR, "split_dataset.py")]
            subprocess.run(split_cmd, cwd=PROJECT_DIR, capture_output=True)
            
            cmd = [
                sys.executable,
                os.path.join(PROJECT_DIR, "train_yolo.py"),
                "--model", req.model,
                "--epochs", str(req.epochs),
                "--batch", str(req.batch),
                "--imgsz", str(req.imgsz),
                "--name", req.name,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=PROJECT_DIR,
            )

            async for line in proc.stdout:
                line_str = line.decode().strip()
                # Parser les epochs (YOLOv8 affiche e.g. "       1/50         0G ...")
                try:
                    parts = line_str.strip().split()
                    if len(parts) > 0 and "/" in parts[0]:
                        nums = parts[0].split("/")
                        if len(nums) == 2 and nums[0].isdigit() and nums[1].isdigit():
                            current = int(nums[0])
                            total = int(nums[1])
                            state.jobs[job_id]["progress"] = round(current / total * 100, 1)
                except Exception:
                    pass

                # Envoyer aux WebSocket clients
                for ws in list(state.training_ws_clients):
                    try:
                        await ws.send_json({
                            "job_id": job_id,
                            "line": line_str,
                            "progress": state.jobs[job_id]["progress"],
                        })
                    except Exception:
                        state.training_ws_clients.remove(ws)

            await proc.wait()
            state.jobs[job_id]["status"] = "completed" if proc.returncode == 0 else "failed"
            state.jobs[job_id]["completed_at"] = datetime.now().isoformat()
            state.jobs[job_id]["progress"] = 100 if proc.returncode == 0 else state.jobs[job_id]["progress"]

            # Recharger le modele
            if proc.returncode == 0:
                state.model = None
                state.load_model()

        except Exception as e:
            state.jobs[job_id]["status"] = "failed"
            state.jobs[job_id]["error"] = str(e)

    asyncio.create_task(run_training())
    return {"job_id": job_id, "status": "started"}


@app.get("/status")
async def get_status():
    """Retourne le statut de tous les jobs."""
    return {"jobs": state.jobs}


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in state.jobs:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return state.jobs[job_id]


@app.get("/metrics")
async def get_metrics():
    """Retourne les metriques du dernier entrainement."""
    results_dir = os.path.join(PROJECT_DIR, "runs", "detect")
    if not os.path.exists(results_dir):
        return {"message": "Aucun entrainement trouve"}

    # Trouver le dernier run
    runs = sorted(
        [d for d in os.listdir(results_dir) if os.path.isdir(os.path.join(results_dir, d))],
        key=lambda d: os.path.getmtime(os.path.join(results_dir, d)),
        reverse=True,
    )

    if not runs:
        return {"message": "Aucun run trouve"}

    run_dir = os.path.join(results_dir, runs[0])
    metrics = {"run_name": runs[0]}

    # Lire results.csv si disponible
    csv_path = os.path.join(run_dir, "results.csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r') as f:
                lines = f.readlines()
            if len(lines) > 1:
                headers = [h.strip() for h in lines[0].split(",")]
                last_values = [v.strip() for v in lines[-1].split(",")]
                for h, v in zip(headers, last_values):
                    try:
                        metrics[h] = float(v)
                    except ValueError:
                        metrics[h] = v

                # Historique complet pour les graphiques
                history = {h: [] for h in headers}
                for line in lines[1:]:
                    values = [v.strip() for v in line.split(",")]
                    for h, v in zip(headers, values):
                        try:
                            history[h].append(float(v))
                        except ValueError:
                            history[h].append(v)
                metrics["history"] = history
        except Exception as e:
            metrics["csv_error"] = str(e)

    return metrics


@app.get("/dataset/stats")
async def get_dataset_stats():
    """Retourne les statistiques du dataset."""
    summary_path = os.path.join(PROJECT_DIR, "output", "dataset", "dataset_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            return json.load(f)

    # Compter manuellement
    images_dir = os.path.join(PROJECT_DIR, "output", "dataset", "images")
    labels_dir = os.path.join(PROJECT_DIR, "output", "dataset", "labels")

    stats = {"images": 0, "labels": 0}
    if os.path.exists(images_dir):
        stats["images"] = len([f for f in os.listdir(images_dir) if f.endswith(('.png', '.jpg'))])
    if os.path.exists(labels_dir):
        stats["labels"] = len([f for f in os.listdir(labels_dir) if f.endswith('.txt')])

    return stats


@app.websocket("/ws/training")
async def training_websocket(websocket: WebSocket):
    """WebSocket pour le suivi en temps reel du training."""
    await websocket.accept()
    state.training_ws_clients.append(websocket)
    try:
        while True:
            # Garder la connexion ouverte, recevoir des pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        state.training_ws_clients.remove(websocket)


# ==========================================================
# NOUVEAUX ENDPOINTS - IMAGES & RESULTATS
# ==========================================================

@app.get("/dataset/images/list")
async def list_dataset_images(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)):
    """Liste paginée des images du dataset avec infos d'annotations."""
    images_dir = os.path.join(PROJECT_DIR, "output", "dataset", "images")
    labels_dir = os.path.join(PROJECT_DIR, "output", "dataset", "labels")

    if not os.path.exists(images_dir):
        return {"images": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}

    all_images = sorted([f for f in os.listdir(images_dir) if f.endswith(('.png', '.jpg', '.jpeg'))])
    total = len(all_images)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    page_images = all_images[start:end]

    result = []
    for img_name in page_images:
        label_name = os.path.splitext(img_name)[0] + ".txt"
        label_path = os.path.join(labels_dir, label_name)
        annotation_count = 0
        classes_found = []
        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                annotation_count = len(lines)
                classes_found = list(set(
                    CLASS_NAMES[int(l.split()[0])]
                    for l in lines
                    if l.split() and int(l.split()[0]) < len(CLASS_NAMES)
                ))

        result.append({
            "filename": img_name,
            "annotation_count": annotation_count,
            "classes": classes_found,
        })

    return {"images": result, "total": total, "page": page, "per_page": per_page, "total_pages": total_pages}


@app.get("/dataset/images/{filename}")
async def serve_dataset_image(filename: str):
    """Sert une image du dataset."""
    filepath = os.path.join(PROJECT_DIR, "output", "dataset", "images", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image introuvable")
    return FileResponse(filepath, media_type="image/png")


@app.get("/dataset/images/{filename}/annotations")
async def get_image_annotations(filename: str):
    """Retourne les annotations YOLO d'une image (converties en coordonnées absolues)."""
    label_name = os.path.splitext(filename)[0] + ".txt"
    label_path = os.path.join(PROJECT_DIR, "output", "dataset", "labels", label_name)

    # Lire la taille de l'image
    img_path = os.path.join(PROJECT_DIR, "output", "dataset", "images", filename)
    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Image introuvable")

    img = Image.open(img_path)
    img_w, img_h = img.size
    img.close()

    annotations = []
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    x_center = float(parts[1]) * img_w
                    y_center = float(parts[2]) * img_h
                    w = float(parts[3]) * img_w
                    h = float(parts[4]) * img_h
                    annotations.append({
                        "class_id": cls_id,
                        "class_name": CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"class_{cls_id}",
                        "bbox": {
                            "x1": round(x_center - w / 2, 1),
                            "y1": round(y_center - h / 2, 1),
                            "x2": round(x_center + w / 2, 1),
                            "y2": round(y_center + h / 2, 1),
                        },
                        "bbox_norm": {
                            "x_center": float(parts[1]),
                            "y_center": float(parts[2]),
                            "width": float(parts[3]),
                            "height": float(parts[4]),
                        },
                    })

    return {
        "filename": filename,
        "image_size": {"width": img_w, "height": img_h},
        "annotations": annotations,
    }


@app.get("/training/results")
async def get_training_results():
    """Retourne un résumé du dernier training avec les fichiers disponibles."""
    results_dir = os.path.join(PROJECT_DIR, "runs", "detect")
    if not os.path.exists(results_dir):
        return {"message": "Aucun entrainement trouvé"}

    runs = sorted(
        [d for d in os.listdir(results_dir) if os.path.isdir(os.path.join(results_dir, d))],
        key=lambda d: os.path.getmtime(os.path.join(results_dir, d)),
        reverse=True,
    )
    if not runs:
        return {"message": "Aucun run trouvé"}

    run_dir = os.path.join(results_dir, runs[0])
    run_name = runs[0]

    # Lister les images disponibles
    available_images = [f for f in os.listdir(run_dir)
                        if f.endswith(('.png', '.jpg')) and os.path.isfile(os.path.join(run_dir, f))]

    # Metriques finales depuis results.csv
    final_metrics = {}
    csv_path = os.path.join(run_dir, "results.csv")
    if os.path.exists(csv_path):
        with open(csv_path, 'r') as f:
            lines = f.readlines()
        if len(lines) > 1:
            headers = [h.strip() for h in lines[0].split(",")]
            last_values = [v.strip() for v in lines[-1].split(",")]
            for h, v in zip(headers, last_values):
                try:
                    final_metrics[h] = round(float(v), 4)
                except ValueError:
                    pass

    # Args du training
    args = {}
    args_path = os.path.join(run_dir, "args.yaml")
    if os.path.exists(args_path):
        try:
            import yaml
            with open(args_path, 'r') as f:
                args = yaml.safe_load(f) or {}
        except Exception:
            pass

    # Poids disponibles
    weights_dir = os.path.join(run_dir, "weights")
    weights = []
    if os.path.exists(weights_dir):
        weights = [f for f in os.listdir(weights_dir) if f.endswith('.pt')]

    return {
        "run_name": run_name,
        "available_images": sorted(available_images),
        "final_metrics": final_metrics,
        "args": args,
        "weights": weights,
        "total_epochs": final_metrics.get("epoch", 0),
    }


@app.get("/training/images/{filename}")
async def serve_training_image(filename: str):
    """Sert une image de résultats d'entraînement."""
    results_dir = os.path.join(PROJECT_DIR, "runs", "detect")
    if not os.path.exists(results_dir):
        raise HTTPException(status_code=404, detail="Aucun run")

    runs = sorted(
        [d for d in os.listdir(results_dir) if os.path.isdir(os.path.join(results_dir, d))],
        key=lambda d: os.path.getmtime(os.path.join(results_dir, d)),
        reverse=True,
    )
    if not runs:
        raise HTTPException(status_code=404, detail="Aucun run")

    filepath = os.path.join(results_dir, runs[0], filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image introuvable")

    media = "image/png" if filename.endswith(".png") else "image/jpeg"
    return FileResponse(filepath, media_type=media)


# ==========================================================
# POINT D'ENTREE
# ==========================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

