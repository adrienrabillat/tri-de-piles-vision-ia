"""
dataset_generator.py
Script principal pour la generation automatique du dataset d'images
annotees pour l'entrainement d'un modele de detection d'objets (YOLO).

Ce script :
  1. Charge la scene de base (.blend)
  2. Pour chaque image du dataset :
     - Randomise l'arriere-plan (couleur de fond, convoyeur)
     - Randomise l'eclairage (intensite, direction)
     - Place des piles aleatoirement au-dessus du convoyeur
     - Simule la gravite (rigid body physics) pour un placement naturel
     - Ajoute des textures procedurales realistes (poussiere, rayures, usure)
     - Ajoute des bornes metalliques aux extremites des piles
     - Randomise la camera (position, angle)
     - Rend l'image en PNG
     - Applique la data augmentation post-rendu
     - Calcule les bounding boxes 2D des piles
     - Exporte les annotations au format YOLO (.txt)
  3. Genere un fichier classes.txt et un resume du dataset

Execution :
    blender --background --python dataset_generator.py
    blender --background --python dataset_generator.py -- --num_images 500 --seed 123

Format YOLO (par ligne) :
    class_id  x_center  y_center  width  height
    (toutes les valeurs sont normalisees entre 0 et 1)
"""

import bpy
import math
import os
import sys
import random
import json
import time
import struct

# Ajouter le dossier du script au path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config

# Import pour la projection 3D -> 2D
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


# ==========================================================
# PARSING DES ARGUMENTS
# ==========================================================

def parse_args():
    """
    Parse les arguments passes apres '--' dans la ligne de commande.
    Ex: blender --background --python script.py -- --num_images 200
    """
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        return {}

    args = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                args[key] = argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1

    return args


# ==========================================================
# VARIATION D'ARRIERE-PLAN
# ==========================================================

def randomize_background():
    """
    Randomise la couleur de fond de la scene et du convoyeur
    pour augmenter la variabilite du dataset.
    """
    # Couleur de fond
    bg_color = random.choice(config.BACKGROUND_COLORS)
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (
        *bg_color, 1.0
    )

    # Couleur et texture du convoyeur
    conv_color = random.choice(config.CONVEYOR_COLORS)
    conveyor = bpy.data.objects.get("Conveyor")
    if conveyor:
        # Creer un nouveau materiau a chaque fois pour varier
        mat = bpy.data.materials.new(name="Mat_Conveyor_Rand")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (600, 0)

        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (300, 0)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        # Texture de base avec bruit pour simuler un metal brosse
        tex_coord = nodes.new(type='ShaderNodeTexCoord')
        tex_coord.location = (-600, 0)

        noise = nodes.new(type='ShaderNodeTexNoise')
        noise.location = (-200, 0)
        noise.inputs['Scale'].default_value = random.uniform(40.0, 80.0)
        noise.inputs['Detail'].default_value = 8.0
        noise.inputs['Roughness'].default_value = 0.6
        links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])

        # Mixer la couleur de base avec le bruit
        mix = nodes.new(type='ShaderNodeMixRGB')
        mix.location = (50, 0)
        mix.inputs['Fac'].default_value = random.uniform(0.05, 0.15)
        mix.inputs['Color1'].default_value = (*conv_color, 1.0)
        darker = tuple(max(0.0, c - 0.08) for c in conv_color)
        mix.inputs['Color2'].default_value = (*darker, 1.0)
        links.new(noise.outputs['Fac'], mix.inputs['Fac'])
        links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])

        # Surface metallique legerement rugueuse
        bsdf.inputs['Metallic'].default_value = random.uniform(0.3, 0.6)
        bsdf.inputs['Roughness'].default_value = random.uniform(0.4, 0.7)

        # Remplacer le materiau existant
        if conveyor.data.materials:
            conveyor.data.materials[0] = mat
        else:
            conveyor.data.materials.append(mat)


# ==========================================================
# GESTION DES PILES (BATTERIES)
# ==========================================================

def clear_batteries():
    """Supprime toutes les piles existantes de la scene."""
    to_delete = [obj for obj in bpy.data.objects if obj.name.startswith("Battery_")]
    for obj in to_delete:
        bpy.data.objects.remove(obj, do_unlink=True)


def get_battery_dimensions(battery_type):
    """
    Retourne (radius, depth) selon le type de pile.
    """
    br = config.BATTERY_RANDOM
    dim_map = {
        "AA": ("radius_AA", "depth_AA"),
        "AAA": ("radius_AAA", "depth_AAA"),
        "button": ("radius_button", "depth_button"),
        "9V": ("radius_9V", "depth_9V"),
        "C": ("radius_C", "depth_C"),
        "D": ("radius_D", "depth_D"),
    }
    keys = dim_map.get(battery_type, ("radius_AA", "depth_AA"))
    return br[keys[0]], br[keys[1]]


def create_battery_texture(bat, battery_type, color):
    """
    Cree un materiau procedural realiste pour une pile.
    Ajoute des bandes, reflets metalliques, variations de couleur,
    poussiere, rayures et usure pour un rendu proche de vraies piles.
    """
    mat = bpy.data.materials.new(name=f"Mat_{bat.name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Node output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (1200, 0)

    # BSDF principal
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (900, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Coordonnees de texture (partagees)
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-1000, 0)

    # --- COULEUR DE BASE ---
    base_color_output = None
    base_roughness = 0.3

    if battery_type == "button":
        # Piles bouton : aspect metallique uniforme
        base_color_node = nodes.new(type='ShaderNodeRGB')
        base_color_node.location = (0, 200)
        base_color_node.outputs[0].default_value = (*color, 1.0)
        base_color_output = base_color_node.outputs[0]
        bsdf.inputs['Metallic'].default_value = 0.9
        base_roughness = random.uniform(0.15, 0.35)
    else:
        # Piles cylindriques : texture avec bandes (etiquette)
        mix = nodes.new(type='ShaderNodeMixRGB')
        mix.location = (0, 200)

        mix.inputs['Color1'].default_value = (*color, 1.0)
        # Couleur secondaire plus contrastee pour simuler les etiquettes
        secondary = tuple(min(1.0, max(0.0, c + random.uniform(-0.3, 0.4))) for c in color)
        mix.inputs['Color2'].default_value = (*secondary, 1.0)

        gradient = nodes.new(type='ShaderNodeTexGradient')
        gradient.location = (-400, 200)
        gradient.gradient_type = 'LINEAR'

        mapping = nodes.new(type='ShaderNodeMapping')
        mapping.location = (-600, 200)
        mapping.inputs['Scale'].default_value = (1, 1, random.uniform(3, 8))

        ramp = nodes.new(type='ShaderNodeValToRGB')
        ramp.location = (-200, 200)
        ramp.color_ramp.elements[0].position = random.uniform(0.3, 0.5)
        ramp.color_ramp.elements[1].position = random.uniform(0.55, 0.75)

        links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
        links.new(mapping.outputs['Vector'], gradient.inputs['Vector'])
        links.new(gradient.outputs['Color'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], mix.inputs['Fac'])
        base_color_output = mix.outputs['Color']

        bsdf.inputs['Metallic'].default_value = random.uniform(0.4, 0.7)
        base_roughness = random.uniform(0.2, 0.5)

        if hasattr(bsdf.inputs, 'Coat Weight'):
            bsdf.inputs['Coat Weight'].default_value = random.uniform(0.1, 0.3)

    # --- POUSSIERE ---
    dust_cfg = config.DUST
    final_color_output = base_color_output

    if dust_cfg.get("enabled", False):
        dust_intensity = random.uniform(*dust_cfg["intensity_range"])

        # Bruit de poussiere
        dust_noise = nodes.new(type='ShaderNodeTexNoise')
        dust_noise.location = (-400, -200)
        dust_noise.inputs['Scale'].default_value = random.uniform(*dust_cfg["noise_scale_range"])
        dust_noise.inputs['Detail'].default_value = dust_cfg.get("noise_detail", 6.0)
        dust_noise.inputs['Roughness'].default_value = random.uniform(0.4, 0.7)

        dust_mapping = nodes.new(type='ShaderNodeMapping')
        dust_mapping.location = (-600, -200)
        # Rotation aleatoire pour varier le motif de poussiere
        dust_mapping.inputs['Rotation'].default_value = (
            random.uniform(0, 6.28),
            random.uniform(0, 6.28),
            random.uniform(0, 6.28),
        )

        links.new(tex_coord.outputs['Object'], dust_mapping.inputs['Vector'])
        links.new(dust_mapping.outputs['Vector'], dust_noise.inputs['Vector'])

        # ColorRamp pour controler la distribution de poussiere
        dust_ramp = nodes.new(type='ShaderNodeValToRGB')
        dust_ramp.location = (-200, -200)
        dust_ramp.color_ramp.elements[0].position = random.uniform(0.3, 0.5)
        dust_ramp.color_ramp.elements[1].position = random.uniform(0.6, 0.85)

        links.new(dust_noise.outputs['Fac'], dust_ramp.inputs['Fac'])

        # Mixer la couleur de poussiere avec la couleur de base
        dust_mix = nodes.new(type='ShaderNodeMixRGB')
        dust_mix.location = (300, -100)
        dust_mix.blend_type = 'MIX'
        dust_color = dust_cfg.get("color", (0.35, 0.30, 0.25))
        dust_mix.inputs['Color2'].default_value = (*dust_color, 1.0)

        # Le facteur de melange = intensite * motif de poussiere
        dust_factor = nodes.new(type='ShaderNodeMath')
        dust_factor.location = (100, -200)
        dust_factor.operation = 'MULTIPLY'
        dust_factor.inputs[1].default_value = dust_intensity

        links.new(dust_ramp.outputs['Color'], dust_factor.inputs[0])
        links.new(dust_factor.outputs['Value'], dust_mix.inputs['Fac'])
        links.new(base_color_output, dust_mix.inputs['Color1'])

        final_color_output = dust_mix.outputs['Color']

        # Augmenter la rugosite dans les zones poussiereuses
        roughness_boost = random.uniform(*dust_cfg.get("roughness_boost", (0.1, 0.3)))
        base_roughness += roughness_boost * dust_intensity

    # --- RAYURES ---
    details_cfg = config.BATTERY_DETAILS
    final_roughness = base_roughness

    if details_cfg.get("scratches", False):
        scratch_voronoi = nodes.new(type='ShaderNodeTexVoronoi')
        scratch_voronoi.location = (-400, -500)
        scratch_voronoi.voronoi_dimensions = '3D'
        scratch_voronoi.feature = 'DISTANCE_TO_EDGE'
        scratch_voronoi.inputs['Scale'].default_value = random.uniform(
            *details_cfg["scratch_scale_range"]
        )

        scratch_mapping = nodes.new(type='ShaderNodeMapping')
        scratch_mapping.location = (-600, -500)
        scratch_mapping.inputs['Scale'].default_value = (
            random.uniform(0.5, 2.0),
            random.uniform(0.5, 2.0),
            random.uniform(3.0, 8.0),  # Etirer pour des rayures longitudinales
        )

        links.new(tex_coord.outputs['Object'], scratch_mapping.inputs['Vector'])
        links.new(scratch_mapping.outputs['Vector'], scratch_voronoi.inputs['Vector'])

        # Inverser et amplifier pour des rayures fines
        scratch_ramp = nodes.new(type='ShaderNodeValToRGB')
        scratch_ramp.location = (-200, -500)
        scratch_ramp.color_ramp.elements[0].position = 0.0
        scratch_ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
        scratch_ramp.color_ramp.elements[1].position = 0.05
        scratch_ramp.color_ramp.elements[1].color = (0, 0, 0, 1)

        links.new(scratch_voronoi.outputs['Distance'], scratch_ramp.inputs['Fac'])

        # Mixer les rayures dans la rugosite
        scratch_intensity = random.uniform(*details_cfg["scratch_intensity_range"])
        scratch_mix = nodes.new(type='ShaderNodeMath')
        scratch_mix.location = (100, -500)
        scratch_mix.operation = 'MULTIPLY'
        scratch_mix.inputs[1].default_value = scratch_intensity

        links.new(scratch_ramp.outputs['Color'], scratch_mix.inputs[0])

        # Ajouter a la rugosite de base
        roughness_add = nodes.new(type='ShaderNodeMath')
        roughness_add.location = (300, -400)
        roughness_add.operation = 'ADD'
        roughness_add.inputs[0].default_value = base_roughness

        links.new(scratch_mix.outputs['Value'], roughness_add.inputs[1])

        # Aussi assombrir legerement la couleur aux endroits rayes
        scratch_darken = nodes.new(type='ShaderNodeMixRGB')
        scratch_darken.location = (500, -200)
        scratch_darken.blend_type = 'MULTIPLY'
        dark_color = tuple(max(0.0, c - 0.15) for c in color)
        scratch_darken.inputs['Color2'].default_value = (*dark_color, 1.0)

        scratch_darken_fac = nodes.new(type='ShaderNodeMath')
        scratch_darken_fac.location = (300, -300)
        scratch_darken_fac.operation = 'MULTIPLY'
        scratch_darken_fac.inputs[1].default_value = scratch_intensity * 2.0

        links.new(scratch_ramp.outputs['Color'], scratch_darken_fac.inputs[0])
        links.new(scratch_darken_fac.outputs['Value'], scratch_darken.inputs['Fac'])
        links.new(final_color_output, scratch_darken.inputs['Color1'])

        final_color_output = scratch_darken.outputs['Color']

        # Connecter la rugosite combinee
        links.new(roughness_add.outputs['Value'], bsdf.inputs['Roughness'])
    else:
        bsdf.inputs['Roughness'].default_value = min(1.0, base_roughness)

    # --- CONNECTER LA COULEUR FINALE ---
    links.new(final_color_output, bsdf.inputs['Base Color'])

    # --- BUMP MAP (micro-relief de surface) ---
    if details_cfg.get("edge_wear", False):
        bump_noise = nodes.new(type='ShaderNodeTexNoise')
        bump_noise.location = (500, -600)
        bump_noise.inputs['Scale'].default_value = random.uniform(30.0, 60.0)
        bump_noise.inputs['Detail'].default_value = 8.0

        links.new(tex_coord.outputs['Object'], bump_noise.inputs['Vector'])

        bump = nodes.new(type='ShaderNodeBump')
        bump.location = (700, -500)
        bump.inputs['Strength'].default_value = random.uniform(
            *details_cfg.get("edge_wear_intensity", (0.1, 0.3))
        )
        bump.inputs['Distance'].default_value = 0.002

        links.new(bump_noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    bat.data.materials.append(mat)


def create_random_battery(index, battery_type=None, existing_positions=None):
    """
    Cree une pile avec position et orientation aleatoires.
    Supporte les occultations partielles entre piles.

    Args:
        index: Numero de la pile (pour nommage unique)
        battery_type: Type force, ou None pour aleatoire
        existing_positions: Liste des positions existantes pour les occultations

    Returns:
        Tuple (objet Blender, type de pile)
    """
    br = config.BATTERY_RANDOM

    # Choisir le type de pile
    if battery_type is None:
        battery_type = random.choices(
            br["types"], weights=br["type_weights"], k=1
        )[0]

    radius, depth = get_battery_dimensions(battery_type)

    # Position aleatoire sur le convoyeur
    x = random.uniform(*br["x_range"])
    y = random.uniform(*br["y_offset_range"])
    z = br["z_base"]

    # Si la gravite est activee, placer les piles en hauteur pour qu'elles tombent
    phys = config.PHYSICS
    if phys.get("enabled", False):
        drop_h = random.uniform(*phys["drop_height_range"])
        # Espacement vertical genereux entre piles pour eviter les interpenetrations
        z = br["z_base"] + drop_h + index * 0.7
        # Espacement horizontal minimum par rapport aux piles existantes
        if existing_positions:
            for _ in range(20):  # Essayer 20 fois de trouver une position libre
                too_close = False
                for ex_pos in existing_positions:
                    dist_xy = math.sqrt((x - ex_pos[0])**2 + (y - ex_pos[1])**2)
                    if dist_xy < 0.4:  # Distance min 40cm
                        too_close = True
                        break
                if not too_close:
                    break
                x = random.uniform(*br["x_range"])
                y = random.uniform(*br["y_offset_range"])
    elif existing_positions and random.random() < 0.3:
        # 30% de chance de placer pres d'une pile existante (occultation)
        ref_pos = random.choice(existing_positions)
        offset = random.uniform(0.2, 0.6) * random.choice([-1, 1])
        x = ref_pos[0] + offset
        y = ref_pos[1] + random.uniform(-0.15, 0.15)
        x = max(br["x_range"][0], min(br["x_range"][1], x))

    # Creer la forme appropriee
    if battery_type == "9V":
        # La pile 9V : proportions realistes 26.5 x 17.5 x 48.5 mm
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(x, y, z),
        )
        bat = bpy.context.active_object
        bat.scale = (0.13, 0.085, depth / 2)  # Largeur, profondeur, hauteur
    else:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius,
            depth=depth,
            location=(x, y, z),
        )
        bat = bpy.context.active_object

    bat.name = f"Battery_{index:03d}"

    # Rotation aleatoire
    rot_z = math.radians(random.uniform(*br["rotation_range"]))
    if battery_type == "button":
        bat.rotation_euler = (0, 0, rot_z)
    elif battery_type == "9V":
        # Les 9V restent generalement debout
        if random.random() < 0.7:
            bat.rotation_euler = (0, 0, rot_z)
            bat.location.z = z + depth / 2
        else:
            bat.rotation_euler = (math.pi / 2, rot_z, 0)
            bat.location.z = z + radius
    else:
        # Les piles cylindriques peuvent etre couchees ou debout
        orientation = random.choice(["debout", "couchee"])
        if orientation == "debout":
            bat.rotation_euler = (0, 0, rot_z)
            bat.location.z = z + depth / 2
        else:
            bat.rotation_euler = (math.pi / 2, rot_z, 0)
            bat.location.z = z + radius

    # Appliquer une texture realiste
    colors = config.BATTERY_COLORS.get(battery_type, [(0.5, 0.5, 0.5)])
    color = random.choice(colors)
    create_battery_texture(bat, battery_type, color)

    # Stocker le type comme propriete custom
    bat["battery_type"] = battery_type
    bat["class_id"] = config.YOLO_CLASSES[battery_type]

    return bat, battery_type


# ==========================================================
# BORNES METALLIQUES (TERMINAL CAPS)
# ==========================================================

def create_terminal_caps(bat, battery_type):
    """
    Ajoute des bornes metalliques realistes aux extremites des piles cylindriques.
    - Borne + (haut) : disque plat qui ferme le cylindre + petit teton fin qui depasse
    - Borne - (bas) : disque plat qui ferme le cylindre

    Appelee APRES la simulation physique pour ne pas interferer.

    Args:
        bat: Objet pile Blender (position finale apres gravite)
        battery_type: Type de pile

    Returns:
        Liste des objets bornes crees
    """
    details = config.BATTERY_DETAILS
    if not details.get("terminal_caps", False):
        return []
    if battery_type in ("button", "9V"):
        return []

    radius, depth = get_battery_dimensions(battery_type)
    cap_color = random.choice(details.get("cap_colors", [(0.75, 0.75, 0.75)]))

    # Materiau metallique brillant pour les bornes
    cap_mat = bpy.data.materials.new(name=f"Mat_Cap_{bat.name}")
    cap_mat.use_nodes = True
    cap_nodes = cap_mat.node_tree.nodes
    cap_nodes.clear()

    cap_bsdf = cap_nodes.new(type='ShaderNodeBsdfPrincipled')
    cap_bsdf.inputs['Base Color'].default_value = (*cap_color, 1.0)
    cap_bsdf.inputs['Metallic'].default_value = 0.95
    cap_bsdf.inputs['Roughness'].default_value = random.uniform(0.08, 0.20)

    cap_output = cap_nodes.new(type='ShaderNodeOutputMaterial')
    cap_mat.node_tree.links.new(cap_bsdf.outputs['BSDF'], cap_output.inputs['Surface'])

    caps = []

    # Determiner l'axe local de la pile
    from mathutils import Vector as Vec
    local_z = bat.matrix_world.to_3x3() @ Vec((0, 0, 1))
    local_z.normalize()
    center = bat.matrix_world.translation

    # --- BORNE - (bas) : disque plat qui ferme le cylindre ---
    flat_depth = 0.008  # Tres fin, juste pour boucher
    offset_neg = local_z * (depth / 2 + flat_depth / 2) * -1
    cap_loc_neg = center + offset_neg

    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius * 1.02,  # Couvre tout le bas
        depth=flat_depth,
        location=cap_loc_neg,
    )
    cap_neg = bpy.context.active_object
    cap_neg.name = f"Cap_-_{bat.name}"
    cap_neg.rotation_euler = bat.rotation_euler.copy()
    cap_neg.data.materials.append(cap_mat)
    cap_neg["is_terminal_cap"] = True
    caps.append(cap_neg)

    # --- BORNE + (haut) : disque plat + petit teton qui depasse ---
    # 1) Disque plat qui ferme le haut
    offset_pos_flat = local_z * (depth / 2 + flat_depth / 2)
    cap_loc_pos_flat = center + offset_pos_flat

    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius * 1.02,
        depth=flat_depth,
        location=cap_loc_pos_flat,
    )
    cap_pos_flat = bpy.context.active_object
    cap_pos_flat.name = f"Cap_+flat_{bat.name}"
    cap_pos_flat.rotation_euler = bat.rotation_euler.copy()
    cap_pos_flat.data.materials.append(cap_mat)
    cap_pos_flat["is_terminal_cap"] = True
    caps.append(cap_pos_flat)

    # 2) Petit teton fin (nub) qui depasse
    nub_radius = radius * 0.28   # ~28% du rayon de la pile (petit pin)
    nub_height = 0.025           # ~2.5mm de hauteur
    offset_nub = local_z * (depth / 2 + flat_depth + nub_height / 2)
    cap_loc_nub = center + offset_nub

    bpy.ops.mesh.primitive_cylinder_add(
        radius=nub_radius,
        depth=nub_height,
        location=cap_loc_nub,
    )
    nub = bpy.context.active_object
    nub.name = f"Cap_+nub_{bat.name}"
    nub.rotation_euler = bat.rotation_euler.copy()
    nub.data.materials.append(cap_mat)
    nub["is_terminal_cap"] = True
    caps.append(nub)

    return caps


# ==========================================================
# SIMULATION DE GRAVITE (RIGID BODY PHYSICS)
# ==========================================================

def setup_rigid_body_world():
    """
    Initialise le monde rigid body de Blender.
    Cree le monde s'il n'existe pas et configure le cache.
    """
    scene = bpy.context.scene
    phys = config.PHYSICS

    # Creer le monde rigid body si necessaire
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()

    rbw = scene.rigidbody_world
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = phys["simulation_frames"]

    # Pas de simulation en temps reel, on bake manuellement
    rbw.enabled = True

    print(f"    [PHYS] Monde rigid body configure ({phys['simulation_frames']} frames)")
    return rbw


def add_conveyor_collision():
    """
    Configure le convoyeur comme corps rigide passif (sol)
    et ajoute des murs invisibles sur les cotes pour empecher
    les piles de tomber du convoyeur.

    Returns:
        Liste des murs crees (pour nettoyage ulterieur)
    """
    phys = config.PHYSICS
    walls = []

    # Convoyeur = corps rigide passif
    conveyor = bpy.data.objects.get("Conveyor")
    if conveyor:
        bpy.context.view_layer.objects.active = conveyor
        conveyor.select_set(True)
        bpy.ops.rigidbody.object_add(type='PASSIVE')
        conveyor.rigid_body.collision_shape = 'BOX'
        conveyor.rigid_body.friction = phys["friction"]
        conveyor.rigid_body.restitution = phys["restitution"]
        conveyor.select_set(False)

    # Murs invisibles sur les bords du convoyeur
    if phys.get("add_walls", True):
        for side in [-1, 1]:
            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(0, side * 0.8, 0.5)
            )
            wall = bpy.context.active_object
            wall.name = f"PhysWall_{'+' if side > 0 else '-'}"
            wall.scale = (12, 0.05, 1.0)
            wall.hide_render = True  # Invisible au rendu

            bpy.ops.rigidbody.object_add(type='PASSIVE')
            wall.rigid_body.collision_shape = 'BOX'
            wall.rigid_body.friction = phys["friction"]
            wall.select_set(False)
            walls.append(wall)

        # Murs aux extremites
        for side_x in [-1, 1]:
            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(side_x * 6, 0, 0.5)
            )
            wall = bpy.context.active_object
            wall.name = f"PhysWallEnd_{'+' if side_x > 0 else '-'}"
            wall.scale = (0.05, 1, 1.0)
            wall.hide_render = True

            bpy.ops.rigidbody.object_add(type='PASSIVE')
            wall.rigid_body.collision_shape = 'BOX'
            wall.rigid_body.friction = phys["friction"]
            wall.select_set(False)
            walls.append(wall)

    print(f"    [PHYS] Convoyeur + {len(walls)} murs configures")
    return walls


def add_battery_rigid_body(bat, battery_type):
    """
    Ajoute un corps rigide actif a une pile.

    Args:
        bat: Objet pile Blender
        battery_type: Type de pile (pour ajuster la masse)
    """
    phys = config.PHYSICS

    bpy.context.view_layer.objects.active = bat
    bat.select_set(True)
    bpy.ops.rigidbody.object_add(type='ACTIVE')

    rb = bat.rigid_body
    rb.collision_shape = 'CONVEX_HULL'
    rb.friction = phys["friction"]
    rb.restitution = phys["restitution"]
    rb.linear_damping = phys["linear_damping"]
    rb.angular_damping = phys["angular_damping"]
    rb.mass = random.uniform(*phys["mass_range"])

    bat.select_set(False)


def simulate_gravity(batteries):
    """
    Lance la simulation physique pour laisser les piles tomber
    et se stabiliser sur le convoyeur.

    Apres simulation :
    - Applique les transforms visuels (position/rotation finales)
    - Supprime les corps rigides

    Args:
        batteries: Liste de tuples (objet, type)
    """
    phys = config.PHYSICS
    scene = bpy.context.scene
    num_frames = phys["simulation_frames"]

    print(f"    [PHYS] Simulation de gravite ({num_frames} frames)...")

    # Liberer le cache existant
    try:
        bpy.ops.ptcache.free_bake_all()
    except RuntimeError:
        pass

    # Remonter a la frame 1
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # Avancer la simulation frame par frame
    for frame in range(1, num_frames + 1):
        scene.frame_set(frame)

    # Appliquer les transforms visuels aux piles
    # (figer leur position/rotation finale)
    for bat, _ in batteries:
        bpy.ops.object.select_all(action='DESELECT')
        bat.select_set(True)
        bpy.context.view_layer.objects.active = bat
        bpy.ops.object.visual_transform_apply()

    bpy.ops.object.select_all(action='DESELECT')

    # Supprimer les corps rigides des piles
    for bat, _ in batteries:
        if bat.rigid_body is not None:
            bpy.context.view_layer.objects.active = bat
            bat.select_set(True)
            bpy.ops.rigidbody.object_remove()
            bat.select_set(False)

    # Revenir a la frame 1
    scene.frame_set(1)

    print("    [PHYS] Simulation terminee, transforms appliques")


def cleanup_physics(walls):
    """
    Nettoie les objets physiques temporaires (murs, rigid body convoyeur).

    Args:
        walls: Liste des murs invisibles a supprimer
    """
    # Supprimer les murs
    for wall in walls:
        bpy.data.objects.remove(wall, do_unlink=True)

    # Retirer le rigid body du convoyeur
    conveyor = bpy.data.objects.get("Conveyor")
    if conveyor and conveyor.rigid_body is not None:
        bpy.context.view_layer.objects.active = conveyor
        conveyor.select_set(True)
        bpy.ops.rigidbody.object_remove()
        conveyor.select_set(False)


# ==========================================================
# RANDOMISATION DE LA CAMERA
# ==========================================================

def look_at(camera, target):
    """
    Oriente la camera pour qu'elle pointe vers un point cible.

    Args:
        camera: Objet camera Blender
        target: Vector ou tuple (x, y, z) du point a viser
    """
    from mathutils import Matrix
    target = Vector(target)
    cam_loc = camera.location

    direction = target - cam_loc
    # Blender : la camera regarde vers -Z local, Y local = haut
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()


def randomize_camera(batteries=None):
    """
    Applique des variations aleatoires a la position de la camera,
    puis la fait pointer vers le barycentre des piles (avec un leger bruit).

    Args:
        batteries: Liste de tuples (objet, type) pour calculer le barycentre.
                   Si None, vise le centre du convoyeur.
    """
    camera = bpy.data.objects.get("Camera_Main")
    if not camera:
        raise RuntimeError("Camera_Main introuvable dans la scene")

    cr = config.CAM_RANDOM

    # Calculer le barycentre des piles
    if batteries and len(batteries) > 0:
        valid_bats = [bat for bat, _ in batteries if bat.location.z >= -1.0]
        if valid_bats:
            avg_x = sum(b.location.x for b in valid_bats) / len(valid_bats)
            avg_y = sum(b.location.y for b in valid_bats) / len(valid_bats)
            avg_z = sum(b.location.z for b in valid_bats) / len(valid_bats)
        else:
            avg_x, avg_y, avg_z = 0, 0, 0.3
    else:
        avg_x, avg_y, avg_z = 0, 0, 0.3

    # Position aleatoire centree sur les piles
    camera.location.x = avg_x + random.uniform(*cr["x_range"])
    camera.location.y = random.uniform(*cr["y_range"])
    camera.location.z = random.uniform(*cr["z_range"])

    # Mise a jour de la focale (randomisation legere)
    base_focal = config.CAMERA_DEFAULTS["focal_length"]
    camera.data.lens = base_focal + random.uniform(-5, 5)

    # Viser le barycentre des piles avec un leger bruit
    noise = cr.get("look_at_noise", 0.5)
    target_x = avg_x + random.uniform(-noise, noise)
    target_y = avg_y + random.uniform(-noise * 0.3, noise * 0.3)
    target_z = avg_z + random.uniform(-0.1, 0.3)
    look_at(camera, (target_x, target_y, target_z))

    # Ajouter un leger roulis
    rz = math.radians(random.uniform(*cr["rot_z_range"]))
    camera.rotation_euler.z += rz

    bpy.context.scene.camera = camera
    return camera


# ==========================================================
# RANDOMISATION DE L'ECLAIRAGE
# ==========================================================

def randomize_lights():
    """
    Applique des variations aleatoires a l'eclairage.
    Simule differentes conditions d'eclairage industriel.
    """
    lr = config.LIGHT_RANDOM

    # Choisir un type d'ambiance lumineuse
    ambiance = random.choice(["neutre", "chaud", "froid", "industriel"])

    for obj in bpy.data.objects:
        if obj.type != 'LIGHT':
            continue

        if obj.name == "Light_Sun":
            obj.data.energy = random.uniform(*lr["sun_energy_range"])
            obj.rotation_euler = (
                math.radians(random.uniform(*lr["sun_rot_x_range"])),
                math.radians(random.uniform(*lr["sun_rot_y_range"])),
                0,
            )
            # Temperature de couleur selon l'ambiance
            if ambiance == "chaud":
                obj.data.color = (1.0, random.uniform(0.85, 0.95), random.uniform(0.7, 0.85))
            elif ambiance == "froid":
                obj.data.color = (random.uniform(0.85, 0.95), random.uniform(0.9, 1.0), 1.0)
            elif ambiance == "industriel":
                obj.data.color = (1.0, random.uniform(0.95, 1.0), random.uniform(0.9, 0.95))
            else:
                obj.data.color = (1.0, 1.0, 1.0)
        elif "Light_Area" in obj.name:
            obj.data.energy = random.uniform(*lr["area_energy_range"])
            # Varier aussi la couleur des area lights
            if ambiance == "chaud":
                obj.data.color = (1.0, 0.95, random.uniform(0.8, 0.9))
            elif ambiance == "froid":
                obj.data.color = (0.9, 0.95, 1.0)
            else:
                obj.data.color = (1.0, 1.0, 1.0)


# ==========================================================
# CALCUL DES BOUNDING BOXES 2D
# ==========================================================

def get_2d_bounding_box(obj, scene, camera):
    """
    Projette les 8 coins du bounding box 3D d'un objet sur l'image 2D
    de la camera, et retourne le rectangle englobant normalise.

    Args:
        obj: Objet Blender
        scene: Scene Blender
        camera: Camera active

    Returns:
        Tuple (x_center, y_center, width, height) normalise [0,1]
        ou None si l'objet est hors champ.
    """
    # Recuperer les 8 coins du bounding box en coordonnees monde
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

    # Projeter chaque coin en coordonnees image 2D
    coords_2d = []
    for corner in bbox_corners:
        co_2d = world_to_camera_view(scene, camera, corner)
        coords_2d.append((co_2d.x, co_2d.y))

    # Calculer le rectangle englobant
    xs = [c[0] for c in coords_2d]
    ys = [c[1] for c in coords_2d]

    x_min = max(0.0, min(xs))
    x_max = min(1.0, max(xs))
    y_min = max(0.0, min(ys))
    y_max = min(1.0, max(ys))

    # Verifier que l'objet est au moins partiellement visible
    if x_min >= x_max or y_min >= y_max:
        return None

    # Verifier la taille minimale (eviter les annotations trop petites)
    width = x_max - x_min
    height = y_max - y_min
    if width < 0.005 or height < 0.005:
        return None

    # Centre et dimensions
    x_center = (x_min + x_max) / 2
    y_center = 1.0 - (y_min + y_max) / 2  # Inverser Y (YOLO: 0 = haut)
    # Note: YOLO utilise y=0 en haut de l'image

    return (x_center, y_center, width, height)


# ==========================================================
# EXPORT YOLO
# ==========================================================

def export_yolo_label(batteries, scene, camera, label_path):
    """
    Genere le fichier d'annotation YOLO pour une image.

    Args:
        batteries: Liste de tuples (objet, type)
        scene: Scene Blender
        camera: Camera active
        label_path: Chemin du fichier .txt

    Returns:
        Nombre d'annotations valides ecrites
    """
    annotations = []
    for bat, bat_type in batteries:
        bbox = get_2d_bounding_box(bat, scene, camera)
        if bbox is None:
            continue

        class_id = config.YOLO_CLASSES[bat_type]
        x_c, y_c, w, h = bbox
        annotations.append(f"{class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}")

    with open(label_path, 'w') as f:
        f.write("\n".join(annotations))

    return len(annotations)


def export_json_metadata(batteries, scene, camera, json_path, image_name):
    """
    Genere un fichier JSON avec des metadonnees detaillees
    (complementaire au format YOLO).

    Args:
        batteries: Liste de tuples (objet, type)
        scene: Scene Blender
        camera: Camera active
        json_path: Chemin du fichier .json
        image_name: Nom du fichier image associe
    """
    metadata = {
        "image": image_name,
        "width": config.RENDER_WIDTH,
        "height": config.RENDER_HEIGHT,
        "camera": {
            "location": list(camera.location),
            "rotation": [math.degrees(r) for r in camera.rotation_euler],
            "focal_length": camera.data.lens,
        },
        "objects": [],
    }

    for bat, bat_type in batteries:
        bbox = get_2d_bounding_box(bat, scene, camera)
        obj_data = {
            "name": bat.name,
            "class": bat_type,
            "class_id": config.YOLO_CLASSES[bat_type],
            "location_3d": list(bat.location),
            "rotation_3d": [math.degrees(r) for r in bat.rotation_euler],
            "visible": bbox is not None,
        }
        if bbox:
            obj_data["bbox_yolo"] = {
                "x_center": round(bbox[0], 6),
                "y_center": round(bbox[1], 6),
                "width": round(bbox[2], 6),
                "height": round(bbox[3], 6),
            }
        metadata["objects"].append(obj_data)

    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)


# ==========================================================
# DATA AUGMENTATION POST-RENDU
# ==========================================================

def apply_augmentation(image_path):
    """
    Applique des augmentations post-rendu a une image PNG.
    Modifie directement les pixels dans le fichier.

    Augmentations :
    - Variation de luminosite
    - Variation de contraste
    - Flou (avec probabilite)

    Utilise les compositing nodes de Blender pour la manipulation d'image.
    """
    aug = config.AUGMENTATION
    if not aug.get("enabled", False):
        return

    scene = bpy.context.scene

    # Activer le compositing
    scene.use_nodes = True

    # Acceder au node tree du compositing
    try:
        tree = scene.node_tree
        if tree is None:
            # Blender 5.x : le compositing node tree peut etre dans
            # bpy.data.node_groups ou necessite une initialisation
            # On tente de forcer la creation
            bpy.ops.node.new_node_tree(type='CompositorNodeTree')
            tree = scene.node_tree
            if tree is None:
                print("    [WARN] Compositing non disponible, augmentation ignoree")
                return
    except (AttributeError, RuntimeError):
        print("    [WARN] Compositing non disponible, augmentation ignoree")
        return

    nodes = tree.nodes
    links = tree.links

    # Nettoyer les nodes existants
    for node in list(nodes):
        nodes.remove(node)

    # Node de rendu (source)
    render_layers = nodes.new(type='CompositorNodeRLayers')
    render_layers.location = (-300, 0)

    # Brightness/Contrast
    bright_contrast = nodes.new(type='CompositorNodeBrightContrast')
    bright_contrast.location = (0, 0)
    brightness_factor = random.uniform(*aug["brightness_range"])
    contrast_factor = random.uniform(*aug["contrast_range"])
    bright_contrast.inputs['Bright'].default_value = (brightness_factor - 1.0) * 50
    bright_contrast.inputs['Contrast'].default_value = (contrast_factor - 1.0) * 50

    links.new(render_layers.outputs['Image'], bright_contrast.inputs['Image'])

    last_output = bright_contrast.outputs['Image']

    # Flou (avec probabilite)
    if random.random() < aug.get("blur_probability", 0.15):
        blur = nodes.new(type='CompositorNodeBlur')
        blur.location = (200, 0)
        blur.size_x = random.uniform(0.5, aug.get("blur_radius_max", 1.5))
        blur.size_y = blur.size_x
        links.new(last_output, blur.inputs['Image'])
        last_output = blur.outputs['Image']

    # Output
    composite = nodes.new(type='CompositorNodeComposite')
    composite.location = (400, 0)
    links.new(last_output, composite.inputs['Image'])


# ==========================================================
# RENDU D'IMAGE
# ==========================================================

def setup_render_for_dataset():
    """Configure le moteur de rendu pour la generation d'images."""
    scene = bpy.context.scene

    # Forcer le moteur de rendu depuis config (override le .blend)
    scene.render.engine = config.RENDER_ENGINE
    print(f"[OK] Moteur de rendu : {config.RENDER_ENGINE}")

    # Si Cycles, configurer les samples
    if "CYCLES" in config.RENDER_ENGINE:
        scene.cycles.samples = config.RENDER_SAMPLES

    scene.render.image_settings.file_format = config.IMAGE_FORMAT
    if config.IMAGE_FORMAT == "JPEG":
        scene.render.image_settings.quality = config.IMAGE_QUALITY

    # Resolution depuis config
    scene.render.resolution_x = config.RENDER_WIDTH
    scene.render.resolution_y = config.RENDER_HEIGHT

    # Desactiver les elements inutiles pour accelerer le rendu
    scene.render.use_stamp = False

    # Utiliser le GPU si disponible (Cycles)
    if scene.render.engine == "CYCLES":
        prefs = bpy.context.preferences.addons.get("cycles")
        if prefs:
            # Detecter automatiquement le type de GPU
            import platform
            if platform.system() == "Darwin":
                gpu_type = "METAL"
            else:
                # Tester OPTIX d'abord (NVIDIA RTX), puis CUDA, sinon NONE
                gpu_type = "NONE"
                for try_type in ["OPTIX", "CUDA"]:
                    try:
                        prefs.preferences.compute_device_type = try_type
                        gpu_type = try_type
                        break
                    except TypeError:
                        continue
            try:
                prefs.preferences.compute_device_type = gpu_type
                bpy.context.scene.cycles.device = "GPU"
                print(f"[OK] GPU active : {gpu_type}")
            except TypeError:
                print("[INFO] Pas de GPU compatible, rendu CPU")


def render_image(filepath):
    """
    Rend l'image courante et la sauvegarde.

    Args:
        filepath: Chemin complet de l'image de sortie (sans extension)
    """
    scene = bpy.context.scene
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)


# ==========================================================
# BOUCLE PRINCIPALE DE GENERATION
# ==========================================================

def generate_dataset(num_images, seed):
    """
    Boucle principale : genere N images avec annotations.

    Args:
        num_images: Nombre d'images a generer
        seed: Graine aleatoire pour la reproductibilite
    """
    random.seed(seed)

    # Creer les dossiers
    config.ensure_directories()

    # Configurer le rendu
    setup_render_for_dataset()

    scene = bpy.context.scene

    # Ecrire le fichier classes.txt (requis par YOLO)
    classes_path = os.path.join(config.DATASET_DIR, "classes.txt")
    with open(classes_path, 'w') as f:
        for name in config.YOLO_CLASS_NAMES:
            f.write(f"{name}\n")
    print(f"[OK] classes.txt ecrit : {classes_path}")

    # Statistiques
    stats = {
        "total_images": 0,
        "total_annotations": 0,
        "per_class": {name: 0 for name in config.YOLO_CLASS_NAMES},
        "skipped_offscreen": 0,
        "render_times": [],
    }

    print(f"\n[START] Generation de {num_images} images (seed={seed})")
    print("=" * 60)

    start_total = time.time()

    max_retries = getattr(config, "MAX_RETRY_PER_IMAGE", 5)

    use_physics = config.PHYSICS.get("enabled", False)

    for i in range(num_images):
        image_name = f"img_{i:05d}"
        image_path = os.path.join(config.IMAGES_DIR, image_name)
        label_path = os.path.join(config.LABELS_DIR, f"{image_name}.txt")
        json_path = os.path.join(config.LABELS_DIR, f"{image_name}.json")

        print(f"\n[{i + 1}/{num_images}] Generation : {image_name}")

        # Boucle de retry : on regenere la scene si aucune pile n'est visible
        for attempt in range(max_retries):
            # 1. Supprimer les piles existantes (et bornes)
            clear_batteries()
            # Supprimer aussi les bornes de l'image precedente
            caps_to_delete = [
                obj for obj in bpy.data.objects
                if obj.name.startswith("Cap_") or obj.get("is_terminal_cap")
            ]
            for cap in caps_to_delete:
                bpy.data.objects.remove(cap, do_unlink=True)

            # 2. Randomiser l'arriere-plan
            randomize_background()

            # 3. Randomiser l'eclairage
            randomize_lights()

            # 4. Placer des piles aleatoires
            br = config.BATTERY_RANDOM
            num_batteries = random.randint(*br["count_range"])
            batteries = []
            existing_positions = []
            for j in range(num_batteries):
                bat, bat_type = create_random_battery(
                    j,
                    existing_positions=existing_positions,
                )
                batteries.append((bat, bat_type))
                existing_positions.append(tuple(bat.location))

            # 5. GRAVITE : simuler la chute des piles
            walls = []
            if use_physics:
                setup_rigid_body_world()
                walls = add_conveyor_collision()
                for bat, bat_type in batteries:
                    add_battery_rigid_body(bat, bat_type)
                simulate_gravity(batteries)

            # 6. Mettre a jour la scene
            bpy.context.view_layer.update()

            # 7. Randomiser la camera (APRES gravite pour viser les piles)
            camera = randomize_camera(batteries=batteries)

            # 8. Verifier AVANT le rendu qu'au moins 1 pile est visible
            test_annot = 0
            for bat, bat_type in batteries:
                # Ignorer les piles tombees trop bas (hors convoyeur)
                if bat.location.z < -1.0:
                    continue
                bbox = get_2d_bounding_box(bat, scene, camera)
                if bbox is not None:
                    test_annot += 1

            if test_annot >= 3:
                break  # OK, au moins 3 piles visibles
            else:
                # Nettoyer la physique avant de retenter
                if walls:
                    cleanup_physics(walls)
                    walls = []
                if attempt < max_retries - 1:
                    print(f"    [RETRY {attempt + 1}] 0 piles visibles, on regenere...")
                else:
                    print(f"    [WARN] Apres {max_retries} tentatives, on garde l'image")

        # 9. Ajouter les bornes metalliques (APRES gravite)
        all_caps = []
        for bat, bat_type in batteries:
            if bat.location.z >= -1.0:  # Pile encore sur le convoyeur
                caps = create_terminal_caps(bat, bat_type)
                all_caps.extend(caps)

        # Nettoyer les murs physiques (avant rendu pour qu'ils ne genent pas)
        if walls:
            cleanup_physics(walls)

        # Compter les stats par classe
        for _, bat_type in batteries:
            stats["per_class"][bat_type] += 1

        if use_physics:
            print(f"    Gravite  : simulation OK, {len(all_caps)} bornes ajoutees")
        print(f"    Piles    : {num_batteries} ({', '.join(t for _, t in batteries)})")
        print(f"    Camera   : ({camera.location.x:.1f}, {camera.location.y:.1f}, {camera.location.z:.1f})")

        # 10. Appliquer la data augmentation (compositing nodes)
        apply_augmentation(image_path)

        # 11. Rendre l'image
        start_render = time.time()
        render_image(image_path)
        render_time = time.time() - start_render
        stats["render_times"].append(render_time)
        print(f"    Rendu    : {render_time:.1f}s")

        # 10. Exporter les annotations YOLO
        num_annot = export_yolo_label(batteries, scene, camera, label_path)
        stats["total_annotations"] += num_annot
        stats["skipped_offscreen"] += len(batteries) - num_annot
        print(f"    Labels   : {num_annot} annotations YOLO")

        # 11. Exporter les metadonnees JSON
        ext = "png" if config.IMAGE_FORMAT == "PNG" else "jpg"
        export_json_metadata(batteries, scene, camera, json_path, f"{image_name}.{ext}")

        stats["total_images"] += 1

    # ==========================================================
    # NETTOYAGE DU COMPOSITING
    # ==========================================================

    bpy.context.scene.use_nodes = False

    # ==========================================================
    # RESUME DU DATASET
    # ==========================================================

    total_time = time.time() - start_total
    avg_render = (
        sum(stats["render_times"]) / len(stats["render_times"])
        if stats["render_times"]
        else 0
    )

    print("\n" + "=" * 60)
    print("RESUME DU DATASET GENERE")
    print("=" * 60)
    print(f"  Images generees     : {stats['total_images']}")
    print(f"  Annotations totales : {stats['total_annotations']}")
    print(f"  Objets hors champ   : {stats['skipped_offscreen']}")
    print(f"  Distribution :")
    for cls_name, count in stats["per_class"].items():
        print(f"    - {cls_name:10s} : {count}")
    print(f"  Temps total         : {total_time:.0f}s")
    print(f"  Temps moyen/image   : {avg_render:.1f}s")
    print(f"  Dossier images      : {config.IMAGES_DIR}")
    print(f"  Dossier labels      : {config.LABELS_DIR}")
    print("=" * 60)

    # Sauvegarder le resume en JSON
    summary_path = os.path.join(config.DATASET_DIR, "dataset_summary.json")
    summary = {
        "num_images": stats["total_images"],
        "num_annotations": stats["total_annotations"],
        "classes": config.YOLO_CLASS_NAMES,
        "per_class_count": stats["per_class"],
        "seed": seed,
        "render_resolution": f"{config.RENDER_WIDTH}x{config.RENDER_HEIGHT}",
        "render_engine": config.RENDER_ENGINE,
        "total_time_seconds": round(total_time, 1),
        "avg_render_seconds": round(avg_render, 1),
    }
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] Resume sauvegarde : {summary_path}")

    print("\n[SUCCESS] Dataset genere avec succes !")


# ==========================================================
# POINT D'ENTREE
# ==========================================================

def main():
    """Point d'entree principal."""
    # Parser les arguments optionnels
    args = parse_args()
    num_images = int(args.get("num_images", config.NUM_IMAGES))
    seed = int(args.get("seed", config.RANDOM_SEED))

    config.print_config()

    # Charger la scene de base
    blend_path = config.BLEND_FILE
    if not os.path.exists(blend_path):
        print(f"[ERREUR] Fichier .blend introuvable : {blend_path}")
        print("[INFO] Executez d'abord scene_generator.py pour creer la scene.")
        sys.exit(1)

    print(f"[INFO] Chargement de la scene : {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    # Generer le dataset
    generate_dataset(num_images, seed)


if __name__ == "__main__":
    main()
