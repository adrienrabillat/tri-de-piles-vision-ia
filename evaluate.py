"""
evaluate.py
Pipeline d'evaluation avancee pour mesurer le reality gap
entre les images synthetiques et les images reelles.

Fonctionnalites :
  - Evaluation du modele sur le test set synthetique
  - Evaluation sur des images reelles (si disponibles)
  - Calcul du reality gap score
  - Analyse de la distribution des predictions
  - Matrice de confusion
  - Analyse des erreurs par classe et par taille d'objet
  - Export des resultats en JSON et visuels

Execution :
    python3 evaluate.py
    python3 evaluate.py --real-images path/to/real/images
    python3 evaluate.py --model runs/detect/battery_sorting/weights/best.pt
"""

import os
import sys
import json
import argparse
import time
from collections import defaultdict, Counter
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluation avancee du modele")
    parser.add_argument(
        "--model", type=str,
        default=os.path.join("runs", "detect", "battery_sorting", "weights", "best.pt"),
        help="Chemin du modele"
    )
    parser.add_argument(
        "--synthetic-dir", type=str,
        default=os.path.join(config.OUTPUT_DIR, "yolo_dataset", "test"),
        help="Dossier des images synthetiques de test"
    )
    parser.add_argument(
        "--real-images", type=str, default=None,
        help="Dossier d'images reelles pour le reality gap"
    )
    parser.add_argument(
        "--conf", type=float, default=0.25,
        help="Seuil de confiance"
    )
    parser.add_argument(
        "--iou", type=float, default=0.5,
        help="Seuil IoU pour le matching"
    )
    parser.add_argument(
        "--output", type=str, default="evaluation_results",
        help="Dossier de sortie"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Afficher les details"
    )
    return parser.parse_args()


# ==========================================================
# METRIQUES
# ==========================================================

def compute_iou(box1, box2):
    """Calcule l'IoU entre deux bounding boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0


def yolo_to_xyxy(yolo_box, img_w, img_h):
    """Convertit YOLO (x_center, y_center, w, h) normalise en (x1, y1, x2, y2) pixels."""
    x_c, y_c, w, h = yolo_box
    x1 = (x_c - w / 2) * img_w
    y1 = (y_c - h / 2) * img_h
    x2 = (x_c + w / 2) * img_w
    y2 = (y_c + h / 2) * img_h
    return [x1, y1, x2, y2]


def load_ground_truth(labels_dir, img_w=1920, img_h=1080):
    """Charge les ground truth depuis les fichiers YOLO."""
    gt = {}
    if not os.path.exists(labels_dir):
        return gt

    for f in os.listdir(labels_dir):
        if not f.endswith('.txt'):
            continue
        name = os.path.splitext(f)[0]
        boxes = []
        with open(os.path.join(labels_dir, f), 'r') as fp:
            for line in fp:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                cls_id = int(parts[0])
                coords = [float(x) for x in parts[1:]]
                xyxy = yolo_to_xyxy(coords, img_w, img_h)
                boxes.append({"class_id": cls_id, "bbox": xyxy})
        gt[name] = boxes
    return gt


def match_predictions_to_gt(preds, gt_boxes, iou_threshold=0.5):
    """
    Match les predictions aux ground truth par IoU.
    Retourne: (TP, FP, FN, matched_pairs)
    """
    matched_gt = set()
    matched_pairs = []
    tp = 0
    fp = 0

    # Trier predictions par confiance decroissante
    preds_sorted = sorted(preds, key=lambda p: p["confidence"], reverse=True)

    for pred in preds_sorted:
        best_iou = 0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(gt_boxes):
            if gt_idx in matched_gt:
                continue
            iou = compute_iou(pred["bbox"], gt["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_iou >= iou_threshold and best_gt_idx >= 0:
            matched_gt.add(best_gt_idx)
            gt = gt_boxes[best_gt_idx]
            if pred["class_id"] == gt["class_id"]:
                tp += 1
            else:
                fp += 1  # Mauvaise classe
            matched_pairs.append({
                "pred": pred,
                "gt": gt,
                "iou": best_iou,
                "correct_class": pred["class_id"] == gt["class_id"],
            })
        else:
            fp += 1  # Pas de match

    fn = len(gt_boxes) - len(matched_gt)
    return tp, fp, fn, matched_pairs


# ==========================================================
# EVALUATION SUR DATASET SYNTHETIQUE
# ==========================================================

def evaluate_synthetic(model, test_dir, conf_threshold, iou_threshold, verbose=False):
    """Evalue le modele sur le test set synthetique."""
    print("\n" + "=" * 60)
    print("EVALUATION SUR DATASET SYNTHETIQUE")
    print("=" * 60)

    images_dir = os.path.join(test_dir, "images")
    labels_dir = os.path.join(test_dir, "labels")

    if not os.path.exists(images_dir):
        print(f"[ERREUR] Dossier images introuvable: {images_dir}")
        return None

    # Charger les ground truth
    gt = load_ground_truth(labels_dir)

    image_files = sorted([f for f in os.listdir(images_dir) if f.endswith(('.png', '.jpg'))])
    print(f"  Images: {len(image_files)}")
    print(f"  Ground truth: {len(gt)} fichiers")

    all_tp, all_fp, all_fn = 0, 0, 0
    per_class_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    confusion_matrix = defaultdict(Counter)  # confusion[gt_class][pred_class]
    size_analysis = {"small": {"tp": 0, "fp": 0, "fn": 0},
                     "medium": {"tp": 0, "fp": 0, "fn": 0},
                     "large": {"tp": 0, "fp": 0, "fn": 0}}
    confidences = []
    inference_times = []

    for img_file in image_files:
        img_path = os.path.join(images_dir, img_file)
        name = os.path.splitext(img_file)[0]

        # Inference
        start = time.time()
        results = model(img_path, conf=conf_threshold, verbose=False)
        inference_times.append((time.time() - start) * 1000)

        # Extraire les predictions
        preds = []
        for r in results:
            if r.boxes is None:
                continue
            for i in range(len(r.boxes)):
                preds.append({
                    "class_id": int(r.boxes.cls[i].item()),
                    "confidence": float(r.boxes.conf[i].item()),
                    "bbox": r.boxes.xyxy[i].tolist(),
                })
                confidences.append(float(r.boxes.conf[i].item()))

        # Matcher avec GT
        gt_boxes = gt.get(name, [])
        tp, fp, fn, matched = match_predictions_to_gt(preds, gt_boxes, iou_threshold)

        all_tp += tp
        all_fp += fp
        all_fn += fn

        # Stats par classe
        for pair in matched:
            gt_cls = pair["gt"]["class_id"]
            pred_cls = pair["pred"]["class_id"]
            confusion_matrix[gt_cls][pred_cls] += 1
            if pair["correct_class"]:
                per_class_stats[gt_cls]["tp"] += 1
            else:
                per_class_stats[gt_cls]["fn"] += 1
                per_class_stats[pred_cls]["fp"] += 1

        # Analyse par taille
        for gt_box in gt_boxes:
            w = gt_box["bbox"][2] - gt_box["bbox"][0]
            h = gt_box["bbox"][3] - gt_box["bbox"][1]
            area = w * h
            if area < 2000:
                size_cat = "small"
            elif area < 10000:
                size_cat = "medium"
            else:
                size_cat = "large"

            # Verifier si ce GT a ete detecte
            detected = any(
                compute_iou(gt_box["bbox"], p["bbox"]) >= iou_threshold
                and p["class_id"] == gt_box["class_id"]
                for p in preds
            )
            if detected:
                size_analysis[size_cat]["tp"] += 1
            else:
                size_analysis[size_cat]["fn"] += 1

    # Calcul des metriques
    precision = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0
    recall = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    avg_inference = sum(inference_times) / len(inference_times) if inference_times else 0
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    results_dict = {
        "dataset": "synthetic",
        "num_images": len(image_files),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "tp": all_tp,
        "fp": all_fp,
        "fn": all_fn,
        "avg_inference_ms": round(avg_inference, 2),
        "avg_confidence": round(avg_confidence, 4),
        "per_class": {},
        "size_analysis": {},
    }

    # Affichage
    print(f"\n  Precision : {precision:.4f}")
    print(f"  Recall    : {recall:.4f}")
    print(f"  F1-Score  : {f1:.4f}")
    print(f"  TP={all_tp}  FP={all_fp}  FN={all_fn}")
    print(f"  Inference : {avg_inference:.1f}ms/img")

    # Par classe
    print(f"\n  Par classe:")
    for cls_id in sorted(per_class_stats.keys()):
        s = per_class_stats[cls_id]
        cls_name = config.YOLO_CLASS_NAMES[cls_id] if cls_id < len(config.YOLO_CLASS_NAMES) else str(cls_id)
        p = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) > 0 else 0
        r = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0
        print(f"    {cls_name:8s}: P={p:.3f} R={r:.3f} TP={s['tp']} FP={s['fp']} FN={s['fn']}")
        results_dict["per_class"][cls_name] = {
            "precision": round(p, 4), "recall": round(r, 4),
            "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
        }

    # Par taille
    print(f"\n  Par taille d'objet:")
    for size_cat in ["small", "medium", "large"]:
        s = size_analysis[size_cat]
        r = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0
        total = s["tp"] + s["fn"]
        print(f"    {size_cat:8s}: Recall={r:.3f} ({s['tp']}/{total})")
        results_dict["size_analysis"][size_cat] = {
            "recall": round(r, 4), "detected": s["tp"], "total": total,
        }

    return results_dict


# ==========================================================
# EVALUATION SUR IMAGES REELLES
# ==========================================================

def evaluate_real(model, real_dir, conf_threshold, verbose=False):
    """
    Evalue le modele sur des images reelles.
    Sans ground truth, on analyse la distribution et la confiance des predictions.
    """
    print("\n" + "=" * 60)
    print("EVALUATION SUR IMAGES REELLES")
    print("=" * 60)

    if not os.path.exists(real_dir):
        print(f"[ERREUR] Dossier introuvable: {real_dir}")
        return None

    image_files = sorted([
        f for f in os.listdir(real_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))
    ])

    if not image_files:
        print("[ERREUR] Aucune image trouvee")
        return None

    print(f"  Images reelles: {len(image_files)}")

    # Si un sous-dossier labels existe, on a des GT
    labels_dir = os.path.join(real_dir, "labels")
    has_gt = os.path.exists(labels_dir)
    gt = load_ground_truth(labels_dir) if has_gt else {}

    if has_gt:
        print(f"  Ground truth: {len(gt)} fichiers")

    class_distribution = Counter()
    confidence_distribution = []
    detections_per_image = []
    inference_times = []
    all_tp, all_fp, all_fn = 0, 0, 0

    for img_file in image_files:
        img_path = os.path.join(real_dir, img_file)
        name = os.path.splitext(img_file)[0]

        start = time.time()
        results = model(img_path, conf=conf_threshold, verbose=False)
        inference_times.append((time.time() - start) * 1000)

        preds = []
        for r in results:
            if r.boxes is None:
                continue
            for i in range(len(r.boxes)):
                cls_id = int(r.boxes.cls[i].item())
                conf_val = float(r.boxes.conf[i].item())
                cls_name = config.YOLO_CLASS_NAMES[cls_id] if cls_id < len(config.YOLO_CLASS_NAMES) else str(cls_id)
                class_distribution[cls_name] += 1
                confidence_distribution.append(conf_val)
                preds.append({
                    "class_id": cls_id,
                    "confidence": conf_val,
                    "bbox": r.boxes.xyxy[i].tolist(),
                })

        detections_per_image.append(len(preds))

        if has_gt and name in gt:
            tp, fp, fn, _ = match_predictions_to_gt(preds, gt[name], 0.5)
            all_tp += tp
            all_fp += fp
            all_fn += fn

        if verbose:
            print(f"    {img_file}: {len(preds)} detections")

    # Resume
    avg_inference = sum(inference_times) / len(inference_times) if inference_times else 0
    avg_conf = sum(confidence_distribution) / len(confidence_distribution) if confidence_distribution else 0
    avg_detections = sum(detections_per_image) / len(detections_per_image) if detections_per_image else 0

    results_dict = {
        "dataset": "real",
        "num_images": len(image_files),
        "has_ground_truth": has_gt,
        "total_detections": sum(detections_per_image),
        "avg_detections_per_image": round(avg_detections, 2),
        "avg_confidence": round(avg_conf, 4),
        "avg_inference_ms": round(avg_inference, 2),
        "class_distribution": dict(class_distribution),
    }

    print(f"\n  Detections totales     : {sum(detections_per_image)}")
    print(f"  Detections/image (moy) : {avg_detections:.1f}")
    print(f"  Confiance moyenne      : {avg_conf:.4f}")
    print(f"  Inference              : {avg_inference:.1f}ms/img")

    print(f"\n  Distribution des classes:")
    for cls_name, count in class_distribution.most_common():
        print(f"    {cls_name:8s}: {count}")

    # Confiance par tranche
    if confidence_distribution:
        bins = [(0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0)]
        print(f"\n  Distribution de confiance:")
        for low, high in bins:
            count = sum(1 for c in confidence_distribution if low <= c < high)
            pct = count / len(confidence_distribution) * 100
            print(f"    [{low:.1f}-{high:.1f}): {count:4d} ({pct:.1f}%)")

    if has_gt:
        precision = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0
        recall = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        results_dict["precision"] = round(precision, 4)
        results_dict["recall"] = round(recall, 4)
        results_dict["f1_score"] = round(f1, 4)
        print(f"\n  Avec ground truth:")
        print(f"    Precision: {precision:.4f}")
        print(f"    Recall   : {recall:.4f}")
        print(f"    F1-Score : {f1:.4f}")

    return results_dict


# ==========================================================
# REALITY GAP SCORE
# ==========================================================

def compute_reality_gap(synthetic_results, real_results):
    """
    Calcule un score de reality gap entre les performances
    sur les images synthetiques vs reelles.

    Score = 0 : pas de gap (ideal)
    Score = 1 : gap maximal
    """
    print("\n" + "=" * 60)
    print("REALITY GAP ANALYSIS")
    print("=" * 60)

    if not synthetic_results or not real_results:
        print("  [SKIP] Donnees insuffisantes")
        return None

    gap_metrics = {}

    # 1. Gap de confiance moyenne
    syn_conf = synthetic_results.get("avg_confidence", 0)
    real_conf = real_results.get("avg_confidence", 0)
    conf_gap = abs(syn_conf - real_conf)
    gap_metrics["confidence_gap"] = round(conf_gap, 4)

    # 2. Gap de detections/image
    syn_det = synthetic_results.get("tp", 0) + synthetic_results.get("fp", 0)
    syn_det_per_img = syn_det / max(1, synthetic_results.get("num_images", 1))
    real_det_per_img = real_results.get("avg_detections_per_image", 0)
    if max(syn_det_per_img, real_det_per_img) > 0:
        det_gap = abs(syn_det_per_img - real_det_per_img) / max(syn_det_per_img, real_det_per_img)
    else:
        det_gap = 0
    gap_metrics["detection_rate_gap"] = round(det_gap, 4)

    # 3. Gap de precision/recall (si GT dispo sur les deux)
    if "precision" in real_results and "precision" in synthetic_results:
        precision_gap = abs(synthetic_results["precision"] - real_results["precision"])
        recall_gap = abs(synthetic_results["recall"] - real_results["recall"])
        gap_metrics["precision_gap"] = round(precision_gap, 4)
        gap_metrics["recall_gap"] = round(recall_gap, 4)

    # 4. Gap de distribution des classes
    syn_dist = synthetic_results.get("per_class", {})
    real_dist = real_results.get("class_distribution", {})
    if syn_dist and real_dist:
        # Normaliser les distributions
        all_classes = set(list(syn_dist.keys()) + list(real_dist.keys()))
        syn_total = sum(v.get("tp", 0) + v.get("fp", 0) for v in syn_dist.values()) if isinstance(list(syn_dist.values())[0], dict) else sum(syn_dist.values())
        real_total = sum(real_dist.values())

        if syn_total > 0 and real_total > 0:
            dist_gaps = []
            for cls in all_classes:
                if isinstance(syn_dist.get(cls, {}), dict):
                    syn_pct = (syn_dist.get(cls, {}).get("tp", 0)) / syn_total
                else:
                    syn_pct = syn_dist.get(cls, 0) / syn_total
                real_pct = real_dist.get(cls, 0) / real_total
                dist_gaps.append(abs(syn_pct - real_pct))
            gap_metrics["class_distribution_gap"] = round(sum(dist_gaps) / len(dist_gaps), 4)

    # Score global (moyenne ponderee)
    weights = {
        "confidence_gap": 0.3,
        "detection_rate_gap": 0.2,
        "precision_gap": 0.2,
        "recall_gap": 0.2,
        "class_distribution_gap": 0.1,
    }

    total_weight = 0
    weighted_sum = 0
    for metric, weight in weights.items():
        if metric in gap_metrics:
            weighted_sum += gap_metrics[metric] * weight
            total_weight += weight

    overall_gap = weighted_sum / total_weight if total_weight > 0 else 0
    gap_metrics["overall_reality_gap"] = round(overall_gap, 4)

    # Interpretation
    if overall_gap < 0.1:
        interpretation = "Excellent - Le modele generalise tres bien aux images reelles"
    elif overall_gap < 0.25:
        interpretation = "Bon - Gap acceptable, le modele devrait fonctionner en conditions reelles"
    elif overall_gap < 0.5:
        interpretation = "Moyen - Gap significatif, ameliorer le domain randomization recommande"
    else:
        interpretation = "Faible - Gap important, le modele aura du mal en conditions reelles"

    gap_metrics["interpretation"] = interpretation

    # Affichage
    print(f"\n  Metriques de gap:")
    for k, v in gap_metrics.items():
        if k != "interpretation":
            print(f"    {k:30s}: {v}")
    print(f"\n  Score global : {overall_gap:.4f}")
    print(f"  Interpretation : {interpretation}")

    # Recommandations
    print(f"\n  Recommandations:")
    if gap_metrics.get("confidence_gap", 0) > 0.15:
        print("    - Les confiances sont tres differentes syn/reel. Augmenter le domain randomization.")
    if gap_metrics.get("detection_rate_gap", 0) > 0.3:
        print("    - Le taux de detection differe. Verifier que les tailles d'objets sont realistes.")
    if gap_metrics.get("class_distribution_gap", 0) > 0.2:
        print("    - La distribution des classes est desequilibree. Ajuster les poids d'echantillonnage.")

    return gap_metrics


# ==========================================================
# MAIN
# ==========================================================

def main():
    args = parse_args()

    print("=" * 60)
    print("PIPELINE D'EVALUATION - Centre de Tri de Piles V3")
    print("=" * 60)

    # Charger le modele
    if not os.path.exists(args.model):
        print(f"[ERREUR] Modele introuvable: {args.model}")
        print("[INFO] Entrainer d'abord avec: python3 train_yolo.py")
        sys.exit(1)

    try:
        from ultralytics import YOLO
        model = YOLO(args.model)
        print(f"[OK] Modele charge: {args.model}")
    except ImportError:
        print("[ERREUR] ultralytics non installe")
        print("[INFO] pip install ultralytics")
        sys.exit(1)

    # Creer le dossier de sortie
    output_dir = os.path.join(config.PROJECT_DIR, args.output)
    os.makedirs(output_dir, exist_ok=True)

    all_results = {}

    # 1. Evaluation synthetique
    synthetic_results = evaluate_synthetic(
        model, args.synthetic_dir, args.conf, args.iou, args.verbose
    )
    if synthetic_results:
        all_results["synthetic"] = synthetic_results

    # 2. Evaluation reelle (si disponible)
    real_results = None
    if args.real_images:
        real_results = evaluate_real(
            model, args.real_images, args.conf, args.verbose
        )
        if real_results:
            all_results["real"] = real_results

    # 3. Reality gap
    if synthetic_results and real_results:
        gap = compute_reality_gap(synthetic_results, real_results)
        if gap:
            all_results["reality_gap"] = gap

    # Sauvegarder les resultats
    results_path = os.path.join(output_dir, "evaluation_results.json")
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[OK] Resultats sauvegardes: {results_path}")

    print("\n[SUCCESS] Evaluation terminee !")


if __name__ == "__main__":
    main()
