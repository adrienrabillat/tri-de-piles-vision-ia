"""
scene_generator.py
Genere la scene 3D du centre de tri de piles dans Blender.
Cree : convoyeur, bacs, capteurs, diverter, camera, lumieres.
Sauvegarde : sorting_plant.blend

Execution dans Blender :
    Methode 1 (console interne) :
        exec(open("/chemin/vers/scene_generator.py").read())

    Methode 2 (ligne de commande) :
        blender --background --python scene_generator.py

Prerequis : Blender 3.x+ avec Python 3.10+
"""

import bpy
import math
import os
import sys

# Ajouter le dossier du script au path pour importer config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config


# ==========================================================
# FONCTIONS DE CREATION DE LA SCENE
# ==========================================================

def clear_scene():
    """Supprime tous les objets de la scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Nettoyer les donnees orphelines
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    print("[OK] Scene nettoyee")


def create_material(name, color, metallic=0.0, roughness=0.5):
    """
    Cree un materiau PBR (Principled BSDF).

    Args:
        name: Nom du materiau
        color: Tuple (R, G, B) avec valeurs entre 0 et 1
        metallic: Valeur metallique (0 = dielectrique, 1 = metal)
        roughness: Rugosite de surface (0 = miroir, 1 = mat)

    Returns:
        Le materiau Blender cree
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness

    output = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    return mat


def create_conveyor():
    """
    Cree le convoyeur principal (tapis roulant).
    Le convoyeur est un cube aplati avec un materiau metallique gris.
    """
    print("[INFO] Creation du convoyeur...")

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    conveyor = bpy.context.active_object
    conveyor.name = "Conveyor"
    conveyor.scale = (10, 1, 0.1)

    mat = create_material("Mat_Conveyor", (0.3, 0.3, 0.3), metallic=0.7, roughness=0.3)
    conveyor.data.materials.append(mat)

    # Propriete pour la vitesse du convoyeur (utilisee dans la simulation)
    conveyor["conveyor_speed"] = 0.5

    return conveyor


def create_bins():
    """
    Cree les bacs de tri, un par categorie de pile + rejet.
    6 classes de piles + 1 bac rejet = 7 bacs.
    """
    print("[INFO] Creation des bacs de tri...")

    bins_config = [
        ("Bin_AA",     (6,  3, 0.5), (0.2, 0.6, 0.2)),   # Vert
        ("Bin_AAA",    (6, -3, 0.5), (0.2, 0.4, 0.8)),   # Bleu
        ("Bin_Button", (8,  3, 0.5), (0.9, 0.7, 0.1)),   # Jaune
        ("Bin_9V",     (8, -3, 0.5), (0.6, 0.3, 0.0)),   # Orange
        ("Bin_C",      (10, 3, 0.5), (0.5, 0.2, 0.6)),   # Violet
        ("Bin_D",      (10,-3, 0.5), (0.3, 0.5, 0.5)),   # Teal
        ("Bin_Reject", (12, 0, 0.5), (0.8, 0.2, 0.2)),   # Rouge
    ]

    bins = []
    for name, location, color in bins_config:
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        bin_obj = bpy.context.active_object
        bin_obj.name = name
        bin_obj.scale = (1.5, 1.5, 1)

        mat = create_material(f"Mat_{name}", color, roughness=0.6)
        bin_obj.data.materials.append(mat)

        bin_obj["bin_type"] = name.split("_")[1]
        bins.append(bin_obj)

    return bins


def create_sensors():
    """
    Cree les capteurs Entry (entree) et ID (identification).
    Ils sont positionnes au-dessus du convoyeur.
    """
    print("[INFO] Creation des capteurs...")

    sensors_config = [
        ("Sensor_Entry", (-4, 0, 0.15), (0.9, 0.5, 0.1)),   # Orange
        ("Sensor_ID",    ( 1, 0, 0.15), (0.5, 0.1, 0.9)),    # Violet
    ]

    sensors = []
    for name, location, color in sensors_config:
        # Capteurs petits et discrets (ne doivent pas dominer la scene)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.08, depth=0.05, location=location
        )
        sensor = bpy.context.active_object
        sensor.name = name
        sensor.rotation_euler = (math.pi / 2, 0, 0)

        # Couleur sombre pour ne pas interferer avec la detection des piles
        mat = create_material(f"Mat_{name}", (0.2, 0.2, 0.2), metallic=0.3, roughness=0.7)
        sensor.data.materials.append(mat)

        sensor["detection_range"] = 0.5
        sensor["sensor_active"] = True
        sensors.append(sensor)

    return sensors


def create_diverter():
    """
    Cree le diverter gate (aiguilleur) pivotant.
    Compose d'une base cylindrique et d'un bras pivotant.
    """
    print("[INFO] Creation du diverter gate...")

    # Base du diverter
    bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=0.3, location=(4, 0, 0))
    base = bpy.context.active_object
    base.name = "Diverter_Base"
    base.rotation_euler = (math.pi / 2, 0, 0)

    mat_base = create_material(
        "Mat_Diverter_Base", (0.4, 0.4, 0.4), metallic=0.9, roughness=0.1
    )
    base.data.materials.append(mat_base)

    # Bras pivotant
    bpy.ops.mesh.primitive_cube_add(size=1, location=(4, 0, 0.5))
    arm = bpy.context.active_object
    arm.name = "Diverter_Arm"
    arm.scale = (0.1, 1.5, 0.3)

    mat_arm = create_material(
        "Mat_Diverter_Arm", (0.8, 0.6, 0.1), metallic=0.5, roughness=0.4
    )
    arm.data.materials.append(mat_arm)

    arm["diverter_state"] = "AA"
    arm["rotation_speed"] = 2.0
    arm.parent = base

    return base, arm


def create_camera():
    """
    Cree la camera principale avec les parametres par defaut de config.py.
    """
    print("[INFO] Creation de la camera...")

    loc = config.CAMERA_DEFAULTS["location"]
    rot = config.CAMERA_DEFAULTS["rotation_deg"]

    bpy.ops.object.camera_add(location=loc)
    camera = bpy.context.active_object
    camera.name = "Camera_Main"
    camera.rotation_euler = (
        math.radians(rot[0]),
        math.radians(rot[1]),
        math.radians(rot[2]),
    )

    # Focale
    camera.data.lens = config.CAMERA_DEFAULTS.get("focal_length", 50)

    bpy.context.scene.camera = camera

    camera["look_at_target"] = "Conveyor"
    camera["use_camera_path"] = False

    return camera


def create_lights():
    """
    Cree l'eclairage de la scene :
    - 1 lumiere soleil (principale)
    - 2 lumieres area (appoint)
    """
    print("[INFO] Creation des lumieres...")

    lights = []

    # Soleil
    bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
    sun = bpy.context.active_object
    sun.name = "Light_Sun"
    sun.data.energy = config.LIGHT_SUN_ENERGY
    sun.rotation_euler = (math.radians(45), math.radians(30), 0)
    lights.append(sun)

    # Lumieres d'appoint
    positions = [(-5, -5, 5), (5, -5, 5)]
    for i, pos in enumerate(positions):
        bpy.ops.object.light_add(type='AREA', location=pos)
        area = bpy.context.active_object
        area.name = f"Light_Area_{i + 1}"
        area.data.energy = config.LIGHT_AREA_ENERGY
        area.data.size = config.LIGHT_AREA_SIZE
        area.rotation_euler = (
            math.radians(60),
            0,
            math.radians(45 * (-1 if i == 0 else 1)),
        )
        lights.append(area)

    return lights


def setup_scene_settings():
    """Configure les parametres globaux de la scene (moteur, resolution, etc.)."""
    print("[INFO] Configuration de la scene...")

    scene = bpy.context.scene

    # Moteur de rendu
    scene.render.engine = config.RENDER_ENGINE
    if config.RENDER_ENGINE == "CYCLES":
        scene.cycles.samples = config.RENDER_SAMPLES
    scene.render.resolution_x = config.RENDER_WIDTH
    scene.render.resolution_y = config.RENDER_HEIGHT
    scene.render.fps = config.RENDER_FPS

    # Fond de la scene (gris tres sombre)
    world = bpy.data.worlds.get("World")
    if world:
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs['Color'].default_value = (0.05, 0.05, 0.05, 1.0)
            bg.inputs['Strength'].default_value = 0.5

    # Timeline
    scene.frame_start = config.FRAME_START
    scene.frame_end = config.FRAME_END


def save_scene(filepath=None):
    """
    Sauvegarde le fichier .blend.
    Si aucun chemin n'est fourni, utilise le chemin defini dans config.py.
    """
    if filepath is None:
        filepath = config.BLEND_FILE

    config.ensure_directories()
    print(f"[INFO] Sauvegarde de la scene : {filepath}")
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    print("[SUCCESS] Scene sauvegardee !")


# ==========================================================
# POINT D'ENTREE
# ==========================================================

def main():
    """Fonction principale de generation de scene."""
    print("=" * 60)
    print("GENERATION DE LA SCENE - CENTRE DE TRI DE PILES")
    print("=" * 60)

    config.print_config()

    clear_scene()

    conveyor = create_conveyor()
    bins = create_bins()
    sensors = create_sensors()
    diverter_base, diverter_arm = create_diverter()
    camera = create_camera()
    lights = create_lights()

    setup_scene_settings()

    # Resume
    print("\n" + "=" * 60)
    print("RESUME DE LA SCENE")
    print("=" * 60)
    print(f"  Convoyeur  : {conveyor.name}")
    print(f"  Bacs       : {len(bins)} ({', '.join(b.name for b in bins)})")
    print(f"  Capteurs   : {len(sensors)} ({', '.join(s.name for s in sensors)})")
    print(f"  Diverter   : {diverter_base.name} + {diverter_arm.name}")
    print(f"  Camera     : {camera.name}")
    print(f"  Lumieres   : {len(lights)}")
    print("=" * 60)

    save_scene()


if __name__ == "__main__":
    main()
