# -*- coding: utf-8 -*-
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from pathlib import Path
import os
#import re
import math
import numpy as np
import argparse
from colorama import init, Fore, Style
import time

# load_obj4c5.py -load 10477_Satellite_v1_L3.obj -ec -scl 0.001 -zr 0.0001 -width 1500 -height 770 -lw 0.3

init()

rgb_colors = {'blue':[0.0,0.0,1.0,1.0],
              'gray':[0.2,0.2,0.2,1.0],
              'black':[0.0,0.0,0.0,1.0],
              'white':[1.0,1.0,1.0,1.0]}

rgb_t = {'blue':[0,0,255],
               'gray':[51,51,51],
               'black':[0,0,0],
               'white':[255,255,255]}

def check_width_value(width):
    val = int(width)
    if val < 800 or val > 1600:
        raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+f"Width value must be less than 1601 and greater than 799."+Fore.RESET+Style.RESET_ALL)
    return val

def check_height_value(height):
    val = int(height)
    if val < 600 or val > 900:
        raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+f"Height value must be less than 901 and greater than 599."+Fore.RESET+Style.RESET_ALL)
    return val

def check_source_ext(file):
    if os.path.exists(file):
        supported_formats = [".obj",".txt"]
        name, ex = os.path.splitext(file)
        if not ex in supported_formats:
            raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+f"Source file must be '.obj' or 'txt' ('{ex}' is not valid)."+Fore.RESET+Style.RESET_ALL)
    else:
        raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+f"FILE NOT FOUND: file or path '{file}' not found."+Fore.RESET+Style.RESET_ALL)
    return file

def check_color(color):
    colors = ['blue','gray','black','white']
    if color not in colors:
        raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+"Background color must be 'blue', 'white', 'gray' or 'black'."+Fore.RESET+Style.RESET_ALL)
    return color

def check_lw(w):
    width = float(w)
    if width < 0.1 or width > 10.0:
        raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+"Line width must be in range 0.1 - 10.0."+Fore.RESET+Style.RESET_ALL)
    return width

def check_positive(v):
    ivalue = float(v)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(Fore.RED+Style.BRIGHT+f"This value must be positive ('{v}' is not valid)."+Fore.RESET+Style.RESET_ALL)
    return ivalue

def load_obj(filename, args):

    vertices: list[list[float]] = []      # v  -> posiciones
    tex_coords: list[list[float]] = []    # vt -> coords de textura (u, v[, w])
    normals: list[list[float]] = []       # vn -> normales
    faces: list[list[dict]] = []          # cada cara = lista de {'v','vt','vn'}
    edges: set[tuple[int, int]] = set()   # edges siguen basados en índice de posición
    num_verts: int = 0
    num_triangles: int = 0
    num_edges: int = 0
    num_vt: int = 0
    num_vn: int = 0
    polygon_verts: int = 0
    load_error: bool = False
    line_counter: int = 0
    color = args.fill_object

    def resolve_index(idx_str, count):
        """Convierte un índice OBJ (1-based, o negativo relativo) a 0-based."""
        if idx_str == '':
            return None
        idx = int(idx_str)
        if idx < 0:
            return count + idx
        return idx - 1

    try:
        with open(filename, 'r') as file:

            for line in file:
                line = line.strip(); line_counter += 1
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if not parts:
                    continue

                # VERTICES (posición)
                if parts[0] == 'v':
                    if len(parts) < 4:
                        continue
                    vertex = [
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3])
                    ]
                    vertices.append(vertex)
                    num_verts += 1

                # COORDENADAS DE TEXTURA
                elif parts[0] == 'vt':
                    if len(parts) < 3:
                        continue
                    u = float(parts[1])
                    v = float(parts[2])
                    w = float(parts[3]) if len(parts) > 3 else 0.0
                    tex_coords.append([u, v, w])
                    num_vt += 1

                # NORMALES
                elif parts[0] == 'vn':
                    if len(parts) < 4:
                        continue
                    nx = float(parts[1])
                    ny = float(parts[2])
                    nz = float(parts[3])
                    normals.append([nx, ny, nz])
                    num_vn += 1

                # FACES
                elif parts[0] == 'f':

                    face_verts: list[dict] = []
                    for part in parts[1:]:

                        # soporta v, v/vt, v//vn, v/vt/vn
                        vals = part.split('/')

                        v_idx = resolve_index(vals[0], len(vertices)) if vals[0] != '' else None
                        vt_idx = None
                        vn_idx = None

                        if len(vals) >= 2:
                            vt_idx = resolve_index(vals[1], len(tex_coords)) if vals[1] != '' else None
                        if len(vals) >= 3:
                            vn_idx = resolve_index(vals[2], len(normals)) if vals[2] != '' else None

                        if v_idx is None:
                            continue

                        face_verts.append({'v': v_idx, 'vt': vt_idx, 'vn': vn_idx})

                    if len(face_verts) < 3:
                        continue

                    polygon_verts = len(face_verts)

                    if color:
                        faces.append(face_verts)

                    num_triangles += 1

                    # generar edges (a partir de los índices de posición)
                    for i in range(len(face_verts)):
                        v1 = face_verts[i]['v']
                        v2 = face_verts[(i + 1) % len(face_verts)]['v']
                        edges.add(tuple(sorted((v1, v2))))

        num_edges = len(edges)

        # CENTERING
        if args.enable_centering and vertices:
            verts_np = np.array(vertices)
            min_v = np.min(verts_np, axis=0)
            max_v = np.max(verts_np, axis=0)
            center = (min_v + max_v) / 2.0

            vertices = [list(np.array(v) - center) for v in vertices]

    except Exception as e:
        print(f"FILE ERROR ON LINE {line_counter}: {str(e)}")
        load_error = True

    return (vertices, edges, num_verts, num_triangles, num_edges, faces,
            polygon_verts, load_error, tex_coords, normals, num_vt, num_vn)


_text_cache: dict = {}

def drawText(f, x, y, text, c, bgc):
    if text not in _text_cache:
        textSurface = f.render(text, True, c, bgc)
        textData = pygame.image.tostring(textSurface, "RGBA", True)
        _text_cache[text] = (textSurface.get_width(), textSurface.get_height(), textData)
    w, h, data = _text_cache[text]
    glWindowPos2d(x, y)
    glDrawPixels(w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)

def show_controls():
    print("\n--------------------- Controls ---------------------")

    print("\nKeyboard Controls (Movement):")
    print("  - Up Arrow: Move the scene forward (rotate upwards)")
    print("  - Down Arrow: Move the scene backward (rotate downwards)")
    print("  - Left Arrow: Move the scene left (rotate left)")
    print("  - Right Arrow: Move the scene right (rotate right)")

    print("\nTranslation Controls:")
    print("  - 'A' Key: Translate scene left")
    print("  - 'S' Key: Translate scene right")
    print("  - 'D' Key: Translate scene up")
    print("  - 'F' Key: Translate scene down")

    print("\nRotation Controls:")
    print("  - 'R' Key: Reset the scene rotation and scaling")
    print("  - 'M' Key: Rotate the scene counterclockwise around the Z-axis")
    print("  - 'N' Key: Rotate the scene clockwise around the Z-axis")

    print("\nView Controls:")
    print("  - 'T' Key: Set top (zenith) view")
    print("  - 'B' Key: Set bottom view")
    print("  - 'J' Key: Set right view")
    print("  - 'L' Key: Set left view")
    print("  - 'G' Key: Set front view")
    print("  - 'K' Key: Set back view")

    print("\nView Mode Toggle:")
    print("  - 'P' Key: Toggle between Orthographic and Perspective views")

    print("\nZoom Controls:")
    print("  - 'Z' Key: Zoom out (decrease scale)")
    print("  - 'X' Key: Zoom in (increase scale)")
    print("  - Mouse Wheel: Zoom in/out")

    print("\nTranslation & Rotation Controls (Drag):")
    print("  - Hold Left Mouse Button: Drag to move the scene")
    print("  - Hold Right Mouse Button: Drag to rotate the scene")

    print("\nLighting:")
    print("  - 'U' Key: Toggle normal-based lighting (requires 'vn' data + -fill)")

    print("\nMiscellaneous:")
    print("  - 'H' Key: Toggle the visibility of on-screen information (model name, scale, view mode)")
    print("  - ESC Key: Exit the program")

    print("\n----------------------------------------------------")



# Clase para manejar cuaterniones
class Quaternion:
    def __init__(self, w, x, y, z):
        self.w = w
        self.x = x
        self.y = y
        self.z = z

    def to_matrix(self):
        ww, xx, yy, zz = self.w * self.w, self.x * self.x, self.y * self.y, self.z * self.z
        wx, wy, wz = self.w * self.x, self.w * self.y, self.w * self.z
        xy, xz, yz = self.x * self.y, self.x * self.z, self.y * self.z

        return np.array([
            [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy), 0],
            [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx), 0],
            [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy), 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)

    def __mul__(self, other):
        w1, x1, y1, z1 = self.w, self.x, self.y, self.z
        w2, x2, y2, z2 = other.w, other.x, other.y, other.z
        return Quaternion(
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        ).normalize()

    def normalize(self):
        mag = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if mag == 0:
            return Quaternion(1, 0, 0, 0)
        return Quaternion(self.w / mag, self.x / mag, self.y / mag, self.z / mag)

# Función para crear un cuaternión de rotación
def create_rotation_quaternion(angle, x, y, z):
    half_angle = math.radians(angle) / 2.0
    sin_half_angle = math.sin(half_angle)
    return Quaternion(math.cos(half_angle), x * sin_half_angle, y * sin_half_angle, z * sin_half_angle)

# Función para inicializar la proyección ortogonal
def setup_view_ortho(display):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()

    aspect_ratio = display[0] / display[1]
    ortho_size = 10
    glOrtho(-ortho_size * 0.5 * aspect_ratio, ortho_size * 0.5 * aspect_ratio, -ortho_size * 0.5, ortho_size * 0.5, -50, 50)

    glMatrixMode(GL_MODELVIEW)

def text_pos(h,p):
    inc_total = (h - 600)
    h_pos = p + inc_total
    return h_pos

# Función para inicializar la proyección en perspectiva
def setup_view_perspective(display):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(50, (display[0] / display[1]), 0.01, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glTranslatef(0.0, 0.0, -10.0)

def fill_object(faces, vertices, normals, use_normals, factor, units):
    """
    Ahora, si el modelo trae 'vn' y se activa use_normals, se emite
    glNormal3fv por cada vértice (usando la normal indicada en la cara)
    antes de emitir la posición, lo que permite iluminación real con
    GL_LIGHTING en vez del relleno plano de color fijo.

    IMPORTANTE: el modo de dibujo (GL_TRIANGLES / GL_QUADS / GL_POLYGON)
    se decide POR CADA CARA según su propio número de vértices, no con
    un único valor global. Si un modelo mezcla triángulos, cuadriláteros
    y n-gons, usar un solo glBegin(modo) para todas las caras corrompe
    el relleno de las que no coinciden con ese modo.
    """
    glEnable(GL_POLYGON_OFFSET_FILL)
    glPolygonOffset(factor, units)

    if not use_normals:
        glColor3f(0.0, 0.5, 0.0)

    for face in faces:
        n = len(face)
        if n == 3:
            mode = GL_TRIANGLES
        elif n == 4:
            mode = GL_QUADS
        else:
            mode = GL_POLYGON

        glBegin(mode)
        for vinfo in face:
            if use_normals and vinfo['vn'] is not None and vinfo['vn'] < len(normals):
                glNormal3fv(normals[vinfo['vn']])
            glVertex3fv(vertices[vinfo['v']])
        glEnd()

    glDisable(GL_POLYGON_OFFSET_FILL)


def window(args):
    # Cargar el modelo OBJ
    try:
        path = args.load_object
        model_name = os.path.basename(path)
        (vertices, edges, num_verts, num_triangles, num_edges, faces,
         polygon_verts, load_error, tex_coords, normals,
         num_vt, num_vn) = load_obj(path, args)

        if not load_error:
            show_controls()
            pygame.init()

            text_bgR = rgb_t[args.bg_color][0]
            text_bgG = rgb_t[args.bg_color][1]
            text_bgB = rgb_t[args.bg_color][2]

            text_pos1 = text_pos(args.window_height,570)
            text_pos2 = text_pos(args.window_height,550)
            text_pos3 = text_pos(args.window_height,530)
            text_pos4 = text_pos(args.window_height,510)
            text_pos5 = text_pos(args.window_height,490)
            text_pos6 = text_pos(args.window_height,470)
            text_pos7 = text_pos(args.window_height,450)
            text_pos8 = text_pos(args.window_height,430)
            vnvt = [text_pos7, text_pos8]
            index = 0

            display = (args.window_width, args.window_height)

            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
            pygame.display.gl_set_attribute(GL_MULTISAMPLESAMPLES, 6)

            pygame.display.set_mode(display, DOUBLEBUF | OPENGL)

            glEnable(GL_MULTISAMPLE)
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

            pygame.display.set_caption("PyMeshGL")
            font = pygame.font.SysFont('arial', 15)

            glEnable(GL_DEPTH_TEST)

            glClearColor(rgb_colors[args.bg_color][0],
                         rgb_colors[args.bg_color][1],
                         rgb_colors[args.bg_color][2],
                         rgb_colors[args.bg_color][3])

            # Preparar iluminación básica (se activa/desactiva con 'U')
            glLightfv(GL_LIGHT0, GL_POSITION, (0.0, 0.0, 1.0, 0.0))
            glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.6, 0.85, 0.6, 1.0))
            glLightfv(GL_LIGHT0, GL_AMBIENT, (0.15, 0.15, 0.15, 1.0))
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            glColor3f(0.0, 0.5, 0.0)

            has_normals = num_vn > 0
            use_normals = False  # se activa con la tecla 'U'
            factor = args.factor
            units = args.units

            ##
            scale = args.scale
            hide_data = False
            green_val = 255
            rotating = False
      
            def build_model_list(use_normals_flag):
                lst = glGenLists(1)
                glNewList(lst, GL_COMPILE)

                glLineWidth(args.line_width)

                if args.fill_object:
                    fill_object(faces, vertices, normals, use_normals_flag, factor, units)

                if args.bg_color == 'white':
                    glColor3f(0.0, 0.0, 0.0)
                    edge_green = 100
                else:
                    glColor3f(1.0, 1.0, 1.0)
                    edge_green = 255

                ordered_edges = sorted(list(edges))

                glBegin(GL_LINES)
                for edge in ordered_edges:
                    for vertex in edge:
                        glVertex3fv(vertices[vertex])
                glEnd()
                glEndList()
                return lst, edge_green

            model_list, green_val = build_model_list(use_normals)

            is_ortho = False
            setup_view_perspective(display)

            quaternion = Quaternion(1, 0, 0, 0)

            dragging = False
            last_mouse_pos = (0, 0)
            translation = [0.0, 0.0]

            clock = pygame.time.Clock()
            last_time = time.perf_counter()
            running = True
            while running:
                now = time.perf_counter()
                dt = min(now - last_time, 0.05)
                last_time = now
                rot_speed = args.rotation_speed * dt
                trans_speed = args.translation_speed * dt

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_h:
                            hide_data = not hide_data
                        elif event.key == pygame.K_u:
                            if has_normals and args.fill_object:
                                use_normals = not use_normals
                                if use_normals:
                                    glEnable(GL_LIGHTING)
                                    glEnable(GL_LIGHT0)
                                else:
                                    glDisable(GL_LIGHTING)
                                    glDisable(GL_LIGHT0)
                                glDeleteLists(model_list, 1)
                                model_list, green_val = build_model_list(use_normals)
                            else:
                                print(Fore.YELLOW + f"No 'vn' data on file '{model_name}' or option '-fill/--fill_object' is not activated." + Fore.RESET)

                        elif event.key == pygame.K_r:
                            quaternion = Quaternion(1, 0, 0, 0)
                            scale = args.scale
                            dragging = False
                            last_mouse_pos = (0, 0)
                            translation = [0.0, 0.0]
                            is_ortho = False
                            setup_view_perspective(display)

                        elif event.key == pygame.K_p:
                            is_ortho = not is_ortho
                            if is_ortho:
                                setup_view_ortho(display)
                            else:
                                setup_view_perspective(display)

                        elif event.key == pygame.K_t:
                            quaternion = Quaternion(1, 0, 0, 0)
                            rotation = create_rotation_quaternion(-90, 1, 0, 0)
                            quaternion = quaternion * rotation
                        elif event.key == pygame.K_b:
                            quaternion = Quaternion(1, 0, 0, 0)
                            rotation = create_rotation_quaternion(90, 1, 0, 0)
                            quaternion = quaternion * rotation
                        elif event.key == pygame.K_j:
                            quaternion = Quaternion(1, 0, 0, 0)
                            rotation = create_rotation_quaternion(90, 0, 1, 0)
                            quaternion = quaternion * rotation
                        elif event.key == pygame.K_l:
                            quaternion = Quaternion(1, 0, 0, 0)
                            rotation = create_rotation_quaternion(-90, 0, 1, 0)
                            quaternion = quaternion * rotation
                        elif event.key == pygame.K_g:
                            quaternion = Quaternion(1, 0, 0, 0)
                            rotation = create_rotation_quaternion(0, 0, 1, 0)
                            quaternion = quaternion * rotation
                        elif event.key == pygame.K_k:
                            quaternion = Quaternion(1, 0, 0, 0)
                            rotation = create_rotation_quaternion(180, 0, 1, 0)
                            quaternion = quaternion * rotation

                    elif event.type == pygame.MOUSEWHEEL:
                        zoom_factor = 1.08 if event.y > 0 else (1/1.08 if event.y < 0 else 1.0)
                        scale *= zoom_factor
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            dragging = True
                            last_mouse_pos = pygame.mouse.get_pos()
                        elif event.button == 3:
                            rotating = True
                            last_mouse_pos = pygame.mouse.get_pos()
                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            dragging = False
                        elif event.button == 3:
                            rotating = False
                    elif event.type == pygame.MOUSEMOTION:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        dx = mouse_x - last_mouse_pos[0]
                        dy = mouse_y - last_mouse_pos[1]
                        if dragging:
                            translation[0] += dx * 0.01
                            translation[1] -= dy * 0.01
                        if rotating:
                            mouse_rot_speed = 120.0 * dt
                            angle_x = dy * -mouse_rot_speed * 0.1
                            angle_y = dx * -mouse_rot_speed * 0.1
                            qx = create_rotation_quaternion(angle_x, 1, 0, 0)
                            qy = create_rotation_quaternion(angle_y, 0, 1, 0)
                            quaternion = quaternion * qx * qy

                        last_mouse_pos = (mouse_x, mouse_y)

                key = pygame.key.get_pressed()

                if key[pygame.K_UP]:
                    rotation = create_rotation_quaternion(rot_speed, 1, 0, 0)
                    quaternion = quaternion * rotation
                if key[pygame.K_DOWN]:
                    rotation = create_rotation_quaternion(-rot_speed, 1, 0, 0)
                    quaternion = quaternion * rotation
                if key[pygame.K_RIGHT]:
                    rotation = create_rotation_quaternion(-rot_speed, 0, 1, 0)
                    quaternion = quaternion * rotation
                if key[pygame.K_LEFT]:
                    rotation = create_rotation_quaternion(rot_speed, 0, 1, 0)
                    quaternion = quaternion * rotation
                if key[pygame.K_m]:
                    rotation = create_rotation_quaternion(rot_speed, 0, 0, 1)
                    quaternion = quaternion * rotation
                if key[pygame.K_n]:
                    rotation = create_rotation_quaternion(-rot_speed, 0, 0, 1)
                    quaternion = quaternion * rotation
                if key[pygame.K_z]:
                    scale -= args.zoom_rate * (dt / (1/60))
                if key[pygame.K_x]:
                    scale += args.zoom_rate * (dt / (1/60))
                if key[pygame.K_a]:
                    translation[0] -= trans_speed
                if key[pygame.K_s]:
                    translation[0] += trans_speed
                if key[pygame.K_d]:
                    translation[1] += trans_speed
                if key[pygame.K_f]:
                    translation[1] -= trans_speed

                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                glPushMatrix()

                glTranslatef(translation[0], translation[1], 0)

                rotation_matrix = quaternion.to_matrix()
                glMultMatrixf(rotation_matrix)

                glScalef(scale, scale, scale)
                glCallList(model_list)

                glPopMatrix()

                if not hide_data:
                    drawText(font, 20, text_pos1, f'Model: {model_name}', (0, green_val, 0, 255), (text_bgR, text_bgG, text_bgB))
                    drawText(font, 20, text_pos2, f'Scale: {round(scale, 6)}', (0, green_val, 0, 255), (text_bgR, text_bgG, text_bgB))
                    view_mode = "Orthographic" if is_ortho else "Perspective"
                    drawText(font, 20, text_pos3, f'View: {view_mode}', (0, green_val, 0, 255),(text_bgR, text_bgG, text_bgB))
                    drawText(font, 20, text_pos4, f'Num Verts: {num_verts}',(0, green_val, 0, 255),(text_bgR, text_bgG, text_bgB))
                    drawText(font, 20, text_pos5, f'Num Faces: {num_triangles}',(0, green_val, 0, 255),(text_bgR, text_bgG, text_bgB))
                    drawText(font, 20, text_pos6, f'Num Edges: {num_edges}',(0, green_val, 0, 255),(text_bgR, text_bgG, text_bgB))
                    if num_vt > 0:
                        drawText(font, 20, vnvt[index], f'Num VT (tex coords): {num_vt}',(0, green_val, 0, 255),(text_bgR, text_bgG, text_bgB))
                        index += 1
                    if num_vn > 0:
                        drawText(font, 20, vnvt[index], f'Num VN (normals): {num_vn} | Lighting: {"ON" if use_normals else "OFF"}',(0, green_val, 0, 255),(text_bgR, text_bgG, text_bgB))
                    index = 0

                pygame.display.flip()
                clock.tick(120)

            glDeleteLists(model_list, 1)
            pygame.quit()
        else:
            print(Fore.RED+Style.BRIGHT + "FILE ERROR" + Fore.RESET+Style.RESET_ALL)
            print("terminated")

    except Exception as e:
        print(Fore.RED+Style.BRIGHT + "UNEXPECTED ERROR: " + e.__str__() + Fore.RESET+Style.RESET_ALL)

def main():
    parser = argparse.ArgumentParser(prog="pymeshgl", conflict_handler='resolve',
                                     description="Show obj models",allow_abbrev=False)
    parser.add_argument('-load','--load_object',required=True,type=check_source_ext,help="Obj model to load")
    parser.add_argument('-width','--window_width',type=check_width_value,default=800,help="Window width (default is 800)")
    parser.add_argument('-height','--window_height',type=check_height_value,default=600,help="Window height (default is 600)")
    parser.add_argument('-bg','--bg_color',type=check_color,default='black',help="Background color (default is 'black')")
    parser.add_argument('-lw','--line_width',type=check_lw,default=1.0,help="Line width (default is 1.0)")
    parser.add_argument('-fill','--fill_object',action='store_true',help="Add solid color to model")
    parser.add_argument('-scl','--scale',type=check_positive,default=1.0,help="Object scale (default is 1.0)")
    parser.add_argument('-zr','--zoom_rate',type=check_positive,default=0.05,help="Zoom Rate (default is 0.05)")
    parser.add_argument('-ec','--enable_centering',action='store_true',help="Enable automatic centering")
    parser.add_argument('-rspd','--rotation_speed',type=check_positive,default=90.0,help="Rotation speed (default is 90.0)")
    parser.add_argument('-tspd','--translation_speed',type=check_positive,default=2.0,help="Translation speed (default is 2.0)")
    parser.add_argument('-f','--factor',type=float,default=1.0,help="Slope Scaling (Slope-Factor). Needs '-fill/--fill_object' stored True")
    parser.add_argument('-u','--units',type=float,default=1.0,help="Minimum Phase Shift Units (Constant-Units). Needs '-fill/--fill_object' stored True")
 
    args = parser.parse_args()
    if (args.factor != 1.0 or args.units != 1.0) and not args.fill_object:
        parser.error("Arguments '-f/--factor' and '-u/--units' only can be used with '-fill/--fill_object' argument stored True")
 
    window(args)

if __name__ =="__main__":
    main()
