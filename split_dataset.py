"""
split_dataset.py
Divise le dataset en ensembles train/val/test pour l'entrainement YOLO.
Genere automatiquement le fichier data.yaml requis par YOLOv5/v8.

Execution :
    python3 split_dataset.py
    python3 split_dataset.py --train 0.8 --val 0.15 --test 0.05
    python3 split_dataset.py --input output/dataset --output output/yolo_dataset

Structure de sortie :
    yolo_dataset/
    ├── train/
    │   ├── images/
    │   └── labels/
    ├── val/
    │   ├── images/
    │   └── labels/
    ├── test/          (optionnel, si test > 0)
    │   ├── images/
    │   └── labels/
    └── data.yaml
"""

import os
import sys
import shutil
import random
import argparse
import yaml

# Ajouter le dossier du script au path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Split dataset en train/val/test pour YOLO"
    )
    parser.add_argument(
        "--input", type=str,
        default=config.DATASET_DIR,
        help="Chemin du dataset source (defaut: output/dataset)"
    )
    parser.add_argument(
        "--output", type=str,
        default=os.path.join(config.OUTPUT_DIR, "yolo_dataset"),
        help="Chemin du dataset de sortie (defaut: output/yolo_dataset)"
    )
    parser.add_argument(
        "--train", type=float, default=0.8,
        help="Proportion du train set (defaut: 0.8)"
    )
    parser.add_argument(
        "--val", type=float, default=0.15,
        help="Proportion du validation set (defaut: 0.15)"
    )
    parser.add_argument(
        "--test", type=float, default=0.05,
        help="Proportion du test set (defaut: 0.05)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Graine aleatoire (defaut: 42)"
    )
    return parser.parse_args()


def split_dataset(input_dir, output_dir, train_ratio, val_ratio, test_ratio, seed):
    """
    Divise le dataset et genere data.yaml.
    """
    # Validation des ratios
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 0.01:
        print(f"[ERREUR] Les ratios doivent sommer a 1.0 (actuellement {total:.2f})")
        sys.exit(1)

    images_dir = os.path.join(input_dir, "images")
    labels_dir = os.path.join(input_dir, "labels")

    # Lister toutes les images
    image_files = sorted([
        f for f in os.listdir(images_dir)
        if f.endswith(('.png', '.jpg', '.jpeg'))
    ])

    if not image_files:
        print(f"[ERREUR] Aucune image trouvee dans {images_dir}")
        sys.exit(1)

    print(f"[INFO] {len(image_files)} images trouvees")

    # Shuffle avec graine
    random.seed(seed)
    random.shuffle(image_files)

    # Calculer les indices de split
    n = len(image_files)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    splits = {
        "train": image_files[:n_train],
        "val": image_files[n_train:n_train + n_val],
    }
    if test_ratio > 0:
        splits["test"] = image_files[n_train + n_val:]

    # Creer les dossiers et copier les fichiers
    for split_name, files in splits.items():
        split_images = os.path.join(output_dir, split_name, "images")
        split_labels = os.path.join(output_dir, split_name, "labels")
        os.makedirs(split_images, exist_ok=True)
        os.makedirs(split_labels, exist_ok=True)

        for img_file in files:
            # Copier l'image
            src_img = os.path.join(images_dir, img_file)
            dst_img = os.path.join(split_images, img_file)
            shutil.copy2(src_img, dst_img)

            # Copier le label .txt
            base_name = os.path.splitext(img_file)[0]
            label_file = f"{base_name}.txt"
            src_label = os.path.join(labels_dir, label_file)
            if os.path.exists(src_label):
                dst_label = os.path.join(split_labels, label_file)
                shutil.copy2(src_label, dst_label)

        print(f"  [{split_name:5s}] {len(files)} images copiees")

    # Generer data.yaml
    data_yaml = {
        "path": os.path.abspath(output_dir),
        "train": "train/images",
        "val": "val/images",
        "nc": len(config.YOLO_CLASS_NAMES),
        "names": config.YOLO_CLASS_NAMES,
    }
    if test_ratio > 0:
        data_yaml["test"] = "test/images"

    yaml_path = os.path.join(output_dir, "data.yaml")
    with open(yaml_path, 'w') as f:
        yaml.dump(data_yaml, f, default_flow_style=False, sort_keys=False)

    print(f"\n[OK] data.yaml genere : {yaml_path}")
    print(f"[OK] Dataset YOLO pret dans : {output_dir}")

    # Resume
    print("\n" + "=" * 50)
    print("RESUME DU SPLIT")
    print("=" * 50)
    for split_name, files in splits.items():
        pct = len(files) / n * 100
        print(f"  {split_name:5s} : {len(files):4d} images ({pct:.0f}%)")
    print(f"  Total : {n} images")
    print(f"  Classes : {config.YOLO_CLASS_NAMES}")
    print("=" * 50)


def main():
    args = parse_args()
    print("[START] Split du dataset")
    print(f"  Source  : {args.input}")
    print(f"  Cible   : {args.output}")
    print(f"  Ratios  : train={args.train}, val={args.val}, test={args.test}")
    print(f"  Seed    : {args.seed}")
    print()

    split_dataset(
        args.input, args.output,
        args.train, args.val, args.test,
        args.seed
    )


if __name__ == "__main__":
    main()
