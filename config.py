"""
config.py
Configuration centralisee pour le projet de centre de tri de piles.
Tous les chemins et parametres sont definis ici pour eviter les chemins
codes en dur et faciliter le deploiement sur differentes machines.

Usage dans Blender :
    Ouvrez la console Python de Blender et executez :
        exec(open("/chemin/vers/config.py").read())
    Ou importez depuis un autre script du meme dossier.

V2 - Ameliorations :
    - Eclairage augmente pour eviter les images trop sombres
    - Camera rapprochee pour des piles plus grandes dans l'image
    - 6 classes de piles (AA, AAA, button, 9V, C, D)
    - Support rendu Cycles (photoreal) en option
    - Data augmentation post-rendu
    - Variation d'arriere-plan
    - Occultations entre piles

V3 - Realisme :
    - Simulation de gravite (rigid body physics) pour placement naturel
    - Poussiere et salissures procedurales sur les piles
    - Rayures et micro-usure de surface
    - Bornes metalliques (+ et -) aux extremites des piles
    - Bump mapping pour relief de surface
"""

import os
import math

# ==========================================================
# CHEMINS - Resolus dynamiquement selon la machine
# ==========================================================

# Repertoire racine du projet = le dossier contenant ce fichier
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Sous-dossiers
BLEND_DIR = os.path.join(PROJECT_DIR, "blend_files")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
DATASET_DIR = os.path.join(OUTPUT_DIR, "dataset")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
LABELS_DIR = os.path.join(DATASET_DIR, "labels")

# Fichier .blend de la scene de base
BLEND_FILE = os.path.join(BLEND_DIR, "sorting_plant.blend")

# ==========================================================
# PARAMETRES DE RENDU
# ==========================================================

RENDER_ENGINE = "BLENDER_EEVEE"       # EEVEE = rapide (~2s/img)
RENDER_SAMPLES = 64                   # Samples EEVEE (suffisant)
RENDER_WIDTH = 1920             # Largeur en pixels
RENDER_HEIGHT = 1080            # Hauteur en pixels
RENDER_FPS = 30                 # Images par seconde (pour video)

# Pour un rendu photoreal (sous-ensemble), mettre RENDER_ENGINE = "CYCLES"
# et augmenter RENDER_SAMPLES a 256-512.

# Format de sortie pour le dataset
IMAGE_FORMAT = "PNG"            # PNG pour la qualite, JPEG pour la taille
IMAGE_QUALITY = 90              # Qualite JPEG (ignore pour PNG)

# ==========================================================
# PARAMETRES DE LA SCENE
# ==========================================================

# Camera par defaut
CAMERA_DEFAULTS = {
    "location": (0, -8, 5),          # Plus proche du convoyeur
    "rotation_deg": (60, 0, 0),     # En degres
    "focal_length": 80,             # Focal plus longue = piles plus grandes dans l'image
}

# Eclairage par defaut
LIGHT_SUN_ENERGY = 5.0              # Augmente pour eviter les images sombres
LIGHT_AREA_ENERGY = 250.0           # Augmente
LIGHT_AREA_SIZE = 3.0

# Timeline
FRAME_START = 1
FRAME_END = 300

# ==========================================================
# PARAMETRES DE RANDOMISATION (Phase 2)
# ==========================================================

RANDOM_SEED = 42                # Pour la reproductibilite

# Nombre d'images a generer dans le dataset
NUM_IMAGES = 100

# Plages de randomisation de la camera
# La camera utilise un systeme "look-at" : elle pointe toujours vers
# le centre du convoyeur, avec de legeres variations aleatoires.
CAM_RANDOM = {
    "x_range": (-1.0, 1.0),        # Deplacement lateral (resserre)
    "y_range": (-6.0, -3.5),       # Beaucoup plus proche du convoyeur
    "z_range": (2.5, 4.5),         # Plus bas pour mieux voir les piles
    "look_at_noise": 0.5,          # Bruit reduit sur le point vise
    "rot_z_range": (-4, 4),        # Roulis plus subtil
}

# Nombre max de tentatives si aucune pile n'est visible
MAX_RETRY_PER_IMAGE = 10

# Plages de randomisation de l'eclairage
LIGHT_RANDOM = {
    "sun_energy_range": (4.0, 8.0),     # Cycles a besoin de plus d'energie
    "sun_rot_x_range": (25, 65),        # Degres - plus de variation
    "sun_rot_y_range": (10, 50),        # Degres - plus de variation
    "area_energy_range": (200, 500),    # Plus fort pour Cycles
}

# Plages de randomisation des piles (batteries)
BATTERY_RANDOM = {
    "count_range": (5, 12),             # Min 5 piles pour eviter les images trop vides
    "x_range": (-3.0, 3.0),            # Position resserree pour garder les piles dans le champ
    "y_offset_range": (-0.4, 0.4),     # Leger decalage lateral (augmente pour occultation)
    "z_base": 0.35,                     # Hauteur de base sur le convoyeur
    "rotation_range": (0, 360),         # Rotation aleatoire (degres)
    "min_spacing": 0.3,                 # Espacement minimum (permet chevauchements)
    # Dimensions par type (echelle ~10x pour visibilite, proportions reelles)
    "radius_AA": 0.07,
    "depth_AA": 0.50,
    "radius_AAA": 0.05,
    "depth_AAA": 0.44,
    "radius_button": 0.10,
    "depth_button": 0.05,
    "radius_9V": 0.13,                  # Pile 9V (rectangulaire simulee ~26x17x48mm)
    "depth_9V": 0.48,
    "radius_C": 0.13,                   # Pile C (rayon ~13mm)
    "depth_C": 0.50,
    "radius_D": 0.17,                   # Pile D (rayon ~17mm)
    "depth_D": 0.61,
    "types": ["AA", "AAA", "button", "9V", "C", "D"],
    "type_weights": [0.25, 0.25, 0.15, 0.15, 0.10, 0.10],
}

# Couleurs des piles par type (R, G, B)
BATTERY_COLORS = {
    "AA": [
        (0.15, 0.15, 0.15),    # Noir / gris fonce
        (0.0, 0.3, 0.6),       # Bleu Duracell
        (0.6, 0.0, 0.0),       # Rouge
        (0.0, 0.5, 0.2),       # Vert GP
        (0.8, 0.6, 0.0),       # Or Duracell
    ],
    "AAA": [
        (0.1, 0.4, 0.1),       # Vert
        (0.5, 0.5, 0.0),       # Jaune/or
        (0.15, 0.15, 0.15),    # Noir
        (0.0, 0.3, 0.6),       # Bleu
        (0.7, 0.2, 0.0),       # Orange
    ],
    "button": [
        (0.7, 0.7, 0.7),       # Argente
        (0.8, 0.7, 0.2),       # Dore
        (0.5, 0.5, 0.5),       # Gris mat
    ],
    "9V": [
        (0.0, 0.3, 0.6),       # Bleu
        (0.15, 0.15, 0.15),    # Noir
        (0.6, 0.5, 0.0),       # Bronze
    ],
    "C": [
        (0.0, 0.5, 0.2),       # Vert
        (0.6, 0.0, 0.0),       # Rouge
        (0.2, 0.2, 0.6),       # Bleu fonce
    ],
    "D": [
        (0.15, 0.15, 0.15),    # Noir
        (0.6, 0.0, 0.0),       # Rouge
        (0.0, 0.3, 0.6),       # Bleu
        (0.8, 0.6, 0.0),       # Or
    ],
}

# ==========================================================
# CLASSES YOLO
# ==========================================================

# Mapping type de pile -> ID de classe YOLO
YOLO_CLASSES = {
    "AA": 0,
    "AAA": 1,
    "button": 2,
    "9V": 3,
    "C": 4,
    "D": 5,
}

# Fichier classes.txt pour YOLO
YOLO_CLASS_NAMES = ["AA", "AAA", "button", "9V", "C", "D"]

# ==========================================================
# VARIATION D'ARRIERE-PLAN
# ==========================================================

# Couleurs de fond aleatoires (R, G, B)
BACKGROUND_COLORS = [
    (0.05, 0.05, 0.05),     # Noir
    (0.15, 0.15, 0.18),     # Gris fonce bleuté
    (0.08, 0.06, 0.04),     # Brun fonce
    (0.20, 0.20, 0.20),     # Gris moyen
    (0.10, 0.12, 0.10),     # Vert fonce
    (0.25, 0.22, 0.18),     # Beige industriel
    (0.12, 0.10, 0.15),     # Violet tres fonce
]

# Couleurs du convoyeur aleatoires
CONVEYOR_COLORS = [
    (0.5, 0.5, 0.5),        # Gris standard
    (0.3, 0.3, 0.35),       # Gris-bleu
    (0.6, 0.6, 0.55),       # Gris clair
    (0.35, 0.30, 0.25),     # Brun metallique
]

# ==========================================================
# DATA AUGMENTATION POST-RENDU
# ==========================================================

AUGMENTATION = {
    "enabled": True,
    "brightness_range": (0.85, 1.15),     # Variation de luminosite
    "contrast_range": (0.9, 1.1),         # Variation de contraste
    "noise_sigma_max": 8,                 # Bruit gaussien (ecart-type max)
    "blur_probability": 0.15,             # Proba d'appliquer un flou
    "blur_radius_max": 1.5,               # Rayon max du flou
}

# ==========================================================
# PHYSIQUE / GRAVITE (Rigid Body)
# ==========================================================

PHYSICS = {
    "enabled": True,
    "drop_height_range": (1.5, 3.0),   # Plus haut pour laisser le temps de se separer
    "simulation_frames": 150,           # Plus de frames pour stabilisation complete
    "friction": 0.7,                    # Plus de friction pour stabiliser
    "restitution": 0.15,               # Moins de rebond
    "linear_damping": 0.6,             # Amortissement fort pour stabiliser vite
    "angular_damping": 0.7,            # Amortissement angulaire fort
    "mass_range": (0.02, 0.15),        # Masse des piles en kg (realiste)
    "add_walls": True,                  # Murs invisibles pour empecher les piles de tomber
}

# ==========================================================
# POUSSIERE / SALISSURES
# ==========================================================

DUST = {
    "enabled": True,
    "intensity_range": (0.10, 0.45),    # Plus de poussiere visible
    "noise_scale_range": (6.0, 20.0),   # Particules plus variees
    "noise_detail": 8.0,                # Plus de detail
    "color": (0.40, 0.33, 0.25),        # Couleur poussiere (brun clair)
    "roughness_boost": (0.15, 0.45),    # Plus de rugosite dans les zones poussiereuses
}

# ==========================================================
# DETAILS REALISTES DES PILES
# ==========================================================

BATTERY_DETAILS = {
    "terminal_caps": True,              # Bornes metalliques aux extremites
    "cap_radius_ratio": 0.50,           # Borne plus large pour bien couvrir le sommet
    "cap_depth": 0.03,                  # Epaisseur de la borne (m)
    "cap_colors": [
        (0.75, 0.75, 0.75),            # Argente (nickel)
        (0.85, 0.80, 0.60),            # Dore (laiton)
        (0.60, 0.60, 0.60),            # Gris acier
    ],
    "scratches": True,                  # Rayures / micro-usure
    "scratch_scale_range": (10.0, 30.0),  # Rayures plus visibles (echelle plus basse)
    "scratch_intensity_range": (0.06, 0.20),  # Rayures plus marquees
    "edge_wear": True,                  # Usure sur les bords
    "edge_wear_intensity": (0.15, 0.45),  # Usure plus prononcee
}

# ==========================================================
# BACKEND API
# ==========================================================

API_HOST = "0.0.0.0"
API_PORT = 8000
# Modele entraine livre avec le projet (remplace par runs/detect/<nom>/weights/best.pt apres un nouvel entrainement)
ONNX_MODEL_PATH = os.path.join(PROJECT_DIR, "weights", "best.onnx")
PT_MODEL_PATH = os.path.join(PROJECT_DIR, "weights", "best.pt")
CONFIDENCE_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

# ==========================================================
# FONCTIONS UTILITAIRES
# ==========================================================

def ensure_directories():
    """Cree tous les repertoires necessaires s'ils n'existent pas."""
    for d in [BLEND_DIR, OUTPUT_DIR, DATASET_DIR, IMAGES_DIR, LABELS_DIR]:
        os.makedirs(d, exist_ok=True)
    print(f"[OK] Repertoires verifies/crees dans : {PROJECT_DIR}")


def deg2rad(degrees):
    """Convertit des degres en radians."""
    return math.radians(degrees)


def print_config():
    """Affiche la configuration actuelle."""
    print("=" * 60)
    print("CONFIGURATION DU PROJET")
    print("=" * 60)
    print(f"  Dossier projet  : {PROJECT_DIR}")
    print(f"  Fichier .blend  : {BLEND_FILE}")
    print(f"  Dossier images  : {IMAGES_DIR}")
    print(f"  Dossier labels  : {LABELS_DIR}")
    print(f"  Moteur rendu    : {RENDER_ENGINE}")
    print(f"  Resolution      : {RENDER_WIDTH}x{RENDER_HEIGHT}")
    print(f"  Nb images       : {NUM_IMAGES}")
    print("=" * 60)


if __name__ == "__main__":
    print_config()
    ensure_directories()
