"""
train_yolo.py
Script cle en main pour entrainer un modele YOLOv8 sur le dataset genere.
Utilise la bibliotheque ultralytics.

Prerequis :
    pip install ultralytics

Execution :
    # Entrainer avec les parametres par defaut
    python3 train_yolo.py

    # Specifier le modele et les epochs
    python3 train_yolo.py --model yolov8s.pt --epochs 100 --batch 16

    # Utiliser un dataset deja split
    python3 train_yolo.py --data output/yolo_dataset/data.yaml

Workflow complet :
    1. blender --background --python dataset_generator.py -- --num_images 500
    2. python3 split_dataset.py
    3. python3 validate_dataset.py --dataset output/yolo_dataset/train
    4. python3 train_yolo.py
"""

import os
import sys
import argparse

# Ajouter le dossier du script au path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Entrainer un modele YOLOv8 sur le dataset de piles"
    )
    parser.add_argument(
        "--data", type=str,
        default=os.path.join(config.OUTPUT_DIR, "yolo_dataset", "data.yaml"),
        help="Chemin vers data.yaml (defaut: output/yolo_dataset/data.yaml)"
    )
    parser.add_argument(
        "--model", type=str, default="yolov8n.pt",
        help="Modele pre-entraine (defaut: yolov8n.pt). Options: yolov8n/s/m/l/x.pt"
    )
    parser.add_argument(
        "--epochs", type=int, default=50,
        help="Nombre d'epochs (defaut: 50)"
    )
    parser.add_argument(
        "--batch", type=int, default=16,
        help="Taille du batch (defaut: 16)"
    )
    parser.add_argument(
        "--imgsz", type=int, default=640,
        help="Taille des images d'entree (defaut: 640)"
    )
    parser.add_argument(
        "--name", type=str, default="battery_sorting",
        help="Nom de l'experience (defaut: battery_sorting)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Reprendre un entrainement interrompu"
    )
    return parser.parse_args()


def check_prerequisites():
    """Verifie les dependances."""
    try:
        import ultralytics
        print(f"[OK] ultralytics v{ultralytics.__version__}")
        return True
    except ImportError:
        print("[ERREUR] ultralytics non installe.")
        print("[INFO]  Installez avec : pip install ultralytics")
        print("[INFO]  Ou : pip install ultralytics[export]")
        return False


def main():
    args = parse_args()

    print("=" * 60)
    print("ENTRAINEMENT YOLO - Centre de Tri de Piles")
    print("=" * 60)

    # Verifier les dependances
    if not check_prerequisites():
        sys.exit(1)

    # Verifier que data.yaml existe
    if not os.path.exists(args.data):
        print(f"[ERREUR] data.yaml introuvable : {args.data}")
        print("[INFO]  Executez d'abord split_dataset.py pour creer le dataset.")
        print("[INFO]  Ou specifiez le chemin avec --data")
        sys.exit(1)

    print(f"\n  Configuration :")
    print(f"    data.yaml : {args.data}")
    print(f"    Modele    : {args.model}")
    print(f"    Epochs    : {args.epochs}")
    print(f"    Batch     : {args.batch}")
    print(f"    Image sz  : {args.imgsz}")
    print(f"    Nom       : {args.name}")
    print()

    from ultralytics import YOLO

    # Charger le modele
    if args.resume:
        # Reprendre l'entrainement
        model = YOLO(f"runs/detect/{args.name}/weights/last.pt")
        print("[INFO] Reprise de l'entrainement...")
    else:
        model = YOLO(args.model)
        print(f"[INFO] Modele pre-entraine charge : {args.model}")

    # Lancer l'entrainement
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        name=args.name,
        patience=10,           # Early stopping apres 10 epochs sans amelioration
        save=True,
        save_period=10,        # Sauvegarder le modele tous les 10 epochs
        plots=True,            # Generer les graphiques de training
        verbose=True,
        # Augmentations integrees YOLO (complementaires aux notres)
        hsv_h=0.015,           # Hue
        hsv_s=0.7,             # Saturation
        hsv_v=0.4,             # Value
        degrees=10,            # Rotation
        translate=0.1,         # Translation
        scale=0.5,             # Scale
        flipud=0.1,            # Flip vertical
        fliplr=0.5,            # Flip horizontal
        mosaic=1.0,            # Mosaic augmentation
        mixup=0.1,             # Mixup
    )

    # Evaluation sur le val set
    print("\n" + "=" * 60)
    print("EVALUATION SUR LE VAL SET")
    print("=" * 60)

    metrics = model.val()
    print(f"\n  mAP50     : {metrics.box.map50:.4f}")
    print(f"  mAP50-95  : {metrics.box.map:.4f}")

    # Exporter le modele en ONNX pour le deploiement
    print("\n[INFO] Export du modele en ONNX...")
    try:
        export_path = model.export(format="onnx")
        print(f"[OK] Modele exporte : {export_path}")
    except Exception as e:
        print(f"[WARN] Export ONNX echoue : {e}")

    print(f"\n[SUCCESS] Entrainement termine !")
    print(f"  Resultats : runs/detect/{args.name}/")
    print(f"  Poids     : runs/detect/{args.name}/weights/best.pt")


if __name__ == "__main__":
    main()
