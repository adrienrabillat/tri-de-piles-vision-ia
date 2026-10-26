"""
run_simulation.py
Pilote la scene existante :
  - charge le .blend genere par scene_generator.py
  - regle camera et lumieres
  - cree des piles avec animation (avancent sur le convoyeur)
  - (optionnel) lance un rendu video

Execution :
    blender --background --python run_simulation.py
    blender sorting_plant.blend --python run_simulation.py
"""

import bpy
import math
import os
import sys

# Ajouter le dossier du script au path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config

# --------------------------------------------------
# 1) Charger la scene generee
# --------------------------------------------------

blend_path = config.BLEND_FILE

if not os.path.exists(blend_path):
    print(f"[ERREUR] Fichier introuvable : {blend_path}")
    print("[INFO] Executez d'abord scene_generator.py pour creer la scene.")
    sys.exit(1)

print(f"[INFO] Ouverture de la scene : {blend_path}")
bpy.ops.wm.open_mainfile(filepath=blend_path)

scene = bpy.context.scene

# --------------------------------------------------
# 2) Gerer la camera
# --------------------------------------------------

camera = bpy.data.objects.get("Camera_Main")
if not camera:
    raise RuntimeError("Camera_Main introuvable dans la scene")

camera.location.z = 10
camera.location.y = -14
camera.rotation_euler = (
    math.radians(65),
    0,
    0,
)

scene.camera = camera
print("[OK] Camera configuree")

# --------------------------------------------------
# 3) Gerer les lumieres
# --------------------------------------------------

for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.name == "Light_Sun":
            obj.data.energy = 4.0
        else:
            obj.data.energy = 200

print("[OK] Lumieres configurees")

# --------------------------------------------------
# 4) Creer des piles
# --------------------------------------------------

def create_battery(name, x):
    """Cree une pile cylindrique sur le convoyeur."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.15,
        depth=0.5,
        location=(x, 0, 0.7),
    )
    bat = bpy.context.active_object
    bat.name = name
    bat["battery_type"] = "AA"
    bat["condition"] = "OK"
    return bat


batteries = [
    create_battery("Battery_1", -4),
    create_battery("Battery_2", -5),
    create_battery("Battery_3", -6),
]

print("[OK] Piles creees")

# --------------------------------------------------
# 5) Animation : piles qui avancent sur le convoyeur
# --------------------------------------------------

scene.frame_start = config.FRAME_START
scene.frame_end = 180  # Animation courte pour la demo

for i, bat in enumerate(batteries):
    start = 1 + i * 15
    end = 140 + i * 15

    bat.location.x = -6
    bat.keyframe_insert("location", frame=start)

    bat.location.x = 6
    bat.keyframe_insert("location", frame=end)

print("[OK] Animation creee")

# --------------------------------------------------
# 6) (Optionnel) Rendu video
# --------------------------------------------------

# Chemin de sortie dynamique
video_path = os.path.join(config.OUTPUT_DIR, "simulation.mp4")
config.ensure_directories()

scene.render.filepath = video_path
scene.render.image_settings.file_format = 'PNG'

# Note : pour le rendu video dans Blender 5.x, utilisez
# scene.render.image_settings.file_format = 'PNG' puis assemblez
# les frames avec ffmpeg, ou rendez directement depuis l'interface.

# Decommentez la ligne ci-dessous pour lancer le rendu (sequence d'images)
# bpy.ops.render.render(animation=True)

print(f"[INFO] Video configuree : {video_path}")
print("[SUCCESS] Simulation prete !")
