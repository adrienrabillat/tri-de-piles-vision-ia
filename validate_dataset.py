"""
validate_dataset.py
Script de validation du dataset genere.
Verifie la coherence entre images et labels, et genere des statistiques.

Execution :
    python3 validate_dataset.py
    python3 validate_dataset.py --dataset output/dataset
    python3 validate_dataset.py --dataset output/yolo_dataset/train

Verifications effectuees :
    - Chaque image a un label .txt correspondant
    - Chaque label reference un class_id valide
    - Les bounding boxes sont dans [0, 1]
    - Pas de fichiers corrompus
    - Statistiques de taille des bboxes
    - Repartition des classes
"""

import os
import sys
import argparse
import json
from collections import Counter

# Ajouter le dossier du script au path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Valide la coherence du dataset YOLO"
    )
    parser.add_argument(
        "--dataset", type=str,
        default=config.DATASET_DIR,
        help="Chemin du dataset a valider (defaut: output/dataset)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Afficher les details pour chaque erreur"
    )
    return parser.parse_args()


def validate_dataset(dataset_dir, verbose=False):
    """
    Valide le dataset et retourne un rapport.
    """
    images_dir = os.path.join(dataset_dir, "images")
    labels_dir = os.path.join(dataset_dir, "labels")

    # Verifier que les dossiers existent
    if not os.path.exists(images_dir):
        print(f"[ERREUR] Dossier images introuvable : {images_dir}")
        return False
    if not os.path.exists(labels_dir):
        print(f"[ERREUR] Dossier labels introuvable : {labels_dir}")
        return False

    # Lister les fichiers
    image_files = set()
    for f in os.listdir(images_dir):
        if f.endswith(('.png', '.jpg', '.jpeg')):
            image_files.add(os.path.splitext(f)[0])

    label_files = set()
    for f in os.listdir(labels_dir):
        if f.endswith('.txt'):
            label_files.add(os.path.splitext(f)[0])

    # Statistiques
    errors = []
    warnings = []
    class_counter = Counter()
    bbox_widths = []
    bbox_heights = []
    bbox_areas = []
    annotations_per_image = []
    empty_labels = 0
    total_annotations = 0
    valid_classes = set(range(len(config.YOLO_CLASS_NAMES)))

    print(f"\n[INFO] Validation de : {dataset_dir}")
    print(f"  Images : {len(image_files)}")
    print(f"  Labels : {len(label_files)}")
    print()

    # 1. Verifier les images sans label
    images_without_labels = image_files - label_files
    if images_without_labels:
        errors.append(f"{len(images_without_labels)} images sans label")
        if verbose:
            for name in sorted(images_without_labels)[:10]:
                print(f"  [ERREUR] Pas de label pour : {name}")

    # 2. Verifier les labels sans image
    labels_without_images = label_files - image_files
    if labels_without_images:
        errors.append(f"{len(labels_without_images)} labels sans image")
        if verbose:
            for name in sorted(labels_without_images)[:10]:
                print(f"  [ERREUR] Pas d'image pour : {name}")

    # 3. Valider chaque fichier label
    common_files = image_files & label_files
    for name in sorted(common_files):
        label_path = os.path.join(labels_dir, f"{name}.txt")

        try:
            with open(label_path, 'r') as f:
                lines = f.readlines()
        except Exception as e:
            errors.append(f"Erreur de lecture : {label_path} ({e})")
            continue

        if not lines or (len(lines) == 1 and not lines[0].strip()):
            empty_labels += 1
            annotations_per_image.append(0)
            continue

        img_annotations = 0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 5:
                errors.append(
                    f"{name}.txt:{line_num} - {len(parts)} colonnes (attendu 5)"
                )
                continue

            try:
                class_id = int(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
            except ValueError as e:
                errors.append(f"{name}.txt:{line_num} - Valeur invalide : {e}")
                continue

            # Verifier le class_id
            if class_id not in valid_classes:
                errors.append(
                    f"{name}.txt:{line_num} - class_id invalide : {class_id} "
                    f"(valides : {valid_classes})"
                )
                continue

            # Verifier que les coordonnees sont dans [0, 1]
            for val_name, val in [("x_center", x_center), ("y_center", y_center),
                                   ("width", width), ("height", height)]:
                if val < 0 or val > 1:
                    warnings.append(
                        f"{name}.txt:{line_num} - {val_name}={val:.4f} hors [0,1]"
                    )

            # Verifier la taille minimale
            if width < 0.001 or height < 0.001:
                warnings.append(
                    f"{name}.txt:{line_num} - bbox trop petite "
                    f"({width:.4f}x{height:.4f})"
                )

            class_counter[class_id] += 1
            bbox_widths.append(width)
            bbox_heights.append(height)
            bbox_areas.append(width * height)
            img_annotations += 1
            total_annotations += 1

        annotations_per_image.append(img_annotations)

    # ==========================================================
    # RAPPORT
    # ==========================================================

    print("=" * 60)
    print("RAPPORT DE VALIDATION")
    print("=" * 60)

    # Erreurs
    if errors:
        print(f"\n🔴 ERREURS ({len(errors)}) :")
        for err in errors[:20]:
            print(f"   {err}")
        if len(errors) > 20:
            print(f"   ... et {len(errors) - 20} autres erreurs")
    else:
        print("\n✅ Aucune erreur detectee")

    # Warnings
    if warnings:
        print(f"\n🟡 AVERTISSEMENTS ({len(warnings)}) :")
        for warn in warnings[:10]:
            print(f"   {warn}")
        if len(warnings) > 10:
            print(f"   ... et {len(warnings) - 10} autres avertissements")
    else:
        print("✅ Aucun avertissement")

    # Stats generales
    print(f"\n📊 STATISTIQUES :")
    print(f"   Images valides          : {len(common_files)}")
    print(f"   Labels vides            : {empty_labels}")
    print(f"   Annotations totales     : {total_annotations}")

    if annotations_per_image:
        avg_annot = sum(annotations_per_image) / len(annotations_per_image)
        print(f"   Annotations/image (moy) : {avg_annot:.1f}")
        print(f"   Annotations/image (min) : {min(annotations_per_image)}")
        print(f"   Annotations/image (max) : {max(annotations_per_image)}")

    # Distribution par classe
    print(f"\n📊 DISTRIBUTION DES CLASSES :")
    for class_id in sorted(class_counter.keys()):
        class_name = config.YOLO_CLASS_NAMES[class_id] if class_id < len(config.YOLO_CLASS_NAMES) else f"INCONNU({class_id})"
        count = class_counter[class_id]
        pct = count / total_annotations * 100 if total_annotations > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"   {class_id} ({class_name:6s}) : {count:5d} ({pct:5.1f}%) {bar}")

    # Stats de taille de bounding box
    if bbox_widths:
        print(f"\n📏 TAILLE DES BOUNDING BOXES (normalise) :")
        print(f"   Largeur : min={min(bbox_widths):.4f}  moy={sum(bbox_widths)/len(bbox_widths):.4f}  max={max(bbox_widths):.4f}")
        print(f"   Hauteur : min={min(bbox_heights):.4f}  moy={sum(bbox_heights)/len(bbox_heights):.4f}  max={max(bbox_heights):.4f}")
        print(f"   Aire    : min={min(bbox_areas):.6f}  moy={sum(bbox_areas)/len(bbox_areas):.6f}  max={max(bbox_areas):.6f}")

        # Detecter les petits objets
        small_threshold = 0.01  # 1% de l'image
        small_objects = sum(1 for a in bbox_areas if a < small_threshold)
        if small_objects > 0:
            pct_small = small_objects / len(bbox_areas) * 100
            print(f"\n   ⚠️  {small_objects} bboxes tres petites (<1% image) = {pct_small:.1f}%")

    print("\n" + "=" * 60)

    is_valid = len(errors) == 0
    print(f"\n{'✅ DATASET VALIDE' if is_valid else '❌ DATASET INVALIDE'}")

    return is_valid


def main():
    args = parse_args()
    is_valid = validate_dataset(args.dataset, args.verbose)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
