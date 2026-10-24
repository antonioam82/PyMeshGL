# -*- coding: utf-8 -*-
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import os
import math
import time
import argparse
from array import array
from dataclasses import dataclass
from typing import Optional

import numpy as np
from colorama import init, Fore, Style

# pymeshgl -load 10477_Satellite_v1_L3.obj -ec -scl 0.001 -zr 0.0001 -width 1500

init()

rgb_colors = {'blue':  [0.0, 0.0, 1.0, 1.0],
              'gray':  [0.2, 0.2, 0.2, 1.0],
              'black': [0.0, 0.0, 0.0, 1.0],
              'white': [1.0, 1.0, 1.0, 1.0]}

rgb_t = {'blue':  [0, 0, 255],
         'gray':  [51, 51, 51],
         'black': [0, 0, 0],
         'white': [255, 255, 255]}

CACHE_SUFFIX = ".pymeshgl.npz"
CACHE_VERSION = 1
FLUSH_EVERY = 900_000          # nº de strings numéricos acumulados antes de convertir a NumPy


# ----------------------------------------------------------------------------
# Validadores de argumentos
# (los textos de error están reconstruidos: sustitúyelos por los tuyos si quieres)
# ----------------------------------------------------------------------------
def check_width_value(width):
    val = int(width)
    if val < 800 or val > 1600:
        raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + "Width value must be between 800 and 1600" + Style.RESET_ALL)
    return val

def check_height_value(height):
    val = int(height)
    if val < 600 or val > 900:
        raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + "Height value must be between 600 and 900" + Style.RESET_ALL)
    return val

def check_source_ext(file):
    if os.path.exists(file):
        supported_formats = [".obj", ".txt"]
        name, ex = os.path.splitext(file)
        if not ex in supported_formats:
            raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + f"Source file format not supported: {ex} (use {', '.join(supported_formats)})" + Style.RESET_ALL)
    else:
        raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + f"FILE NOT FOUND: {file}" + Style.RESET_ALL)
    return file

def check_color(color):
    colors = ['blue', 'gray', 'black', 'white']
    if color not in colors:
        raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + f"Background color must be one of: {', '.join(colors)}" + Style.RESET_ALL)
    return color

def check_lw(w):
    width = float(w)
    if width < 0.1 or width > 10.0:
        raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + "Line width must be between 0.1 and 10.0" + Style.RESET_ALL)
    return width

def check_positive(v):
    ivalue = float(v)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(Fore.RED + Style.BRIGHT + f"This value must be greater than 0 (got {v})" + Style.RESET_ALL)
    return ivalue


# ----------------------------------------------------------------------------
# Carga del modelo
# ----------------------------------------------------------------------------
@dataclass
class Mesh:
    vertices: np.ndarray                 # (N, 3) float32
    edges: np.ndarray                    # (M, 2) uint32, únicas y ordenadas
    normals: np.ndarray                  # (K, 3) float32
    tri_v: Optional[np.ndarray]          # (T*3,) uint32  índices de posición (triangulado en abanico)
    tri_vn: Optional[np.ndarray]         # (T*3,) int32   índices de normal (-1 = sin normal)
    num_verts: int
    num_faces: int
    num_edges: int
    num_vt: int
    num_vn: int
    # Solo se rellenan con keep_raw=True (herramientas de diagnóstico, ver load_obj_legacy)
    poly_v: Optional[np.ndarray] = None      # índices de posición por cara, aplanados
    poly_vt: Optional[np.ndarray] = None     # índices de textura (-1 = sin vt)
    poly_vn: Optional[np.ndarray] = None     # índices de normal (-1 = sin vn)
    poly_len: Optional[np.ndarray] = None    # nº de vértices de cada cara
    tex_coords: Optional[list] = None        # [[u, v, w], ...]
    last_poly_verts: int = 0                 # nº de vértices de la última cara leída


class ObjParseError(ValueError):
    """Error de lectura que ya incluye el número de línea exacto."""


def _flush(flat, chunks, lines):
    """Convierte los strings acumulados a un bloque float32 (N,3).

    `lines` guarda el nº de línea del archivo de cada vértice pendiente; solo se usa
    para señalar la línea exacta si algún valor no es un número válido.
    """
    if flat:
        try:
            chunks.append(np.array(flat, dtype=np.float32).reshape(-1, 3))
        except ValueError as e:
            for i, tok in enumerate(flat):
                try:
                    float(tok)
                except ValueError:
                    raise ObjParseError(
                        f"LINE {lines[i // 3]}: could not convert string to float: {tok!r}") from e
            raise
        flat.clear()
        del lines[:]


def parse_obj(filename, need_faces, keep_raw=False):
    """Parsea el OBJ sin diccionarios por vértice y construye aristas/triángulos con NumPy.

    keep_raw=True conserva además la estructura original de polígonos y las coords de
    textura (más memoria): solo para diagnóstico, no lo uses en el visor.
    """
    v_flat, n_flat = [], []
    v_chunks, n_chunks = [], []
    v_lines, n_lines = array('i'), array('i')   # nº de línea de cada v / vn pendiente de convertir
    face_v = array('i')      # índices de posición de todas las caras, aplanados
    face_vn = array('i')     # índices de normal (solo si need_faces o keep_raw)
    face_vt = array('i')     # índices de textura (solo si keep_raw)
    face_len = array('i')    # nº de vértices de cada cara
    tex_list = []            # coords de textura (solo si keep_raw)
    want_vn = need_faces or keep_raw
    nv = nvt = nvn = nf = 0
    line_counter = 0

    try:
        with open(filename, 'r', errors='replace') as fh:
            for line in fh:
                line_counter += 1
                parts = line.split()
                if not parts:
                    continue
                tag = parts[0]

                if tag == 'v':
                    if len(parts) < 4:
                        continue
                    v_flat.extend(parts[1:4])
                    v_lines.append(line_counter)
                    nv += 1
                    if len(v_flat) >= FLUSH_EVERY:
                        _flush(v_flat, v_chunks, v_lines)

                elif tag == 'f':
                    fv, fn, ft = [], [], []
                    for tok in parts[1:]:
                        # soporta v, v/vt, v//vn, v/vt/vn y índices negativos
                        if '/' in tok:
                            vals = tok.split('/')
                            if not vals[0]:
                                continue
                            vi = int(vals[0])
                            ni = -1
                            ti = -1
                            if want_vn and len(vals) >= 3 and vals[2]:
                                k = int(vals[2])
                                ni = nvn + k if k < 0 else k - 1
                            if keep_raw and len(vals) >= 2 and vals[1]:
                                k = int(vals[1])
                                ti = nvt + k if k < 0 else k - 1
                        else:
                            vi = int(tok)
                            ni = -1
                            ti = -1
                        fv.append(nv + vi if vi < 0 else vi - 1)
                        fn.append(ni)
                        ft.append(ti)

                    if len(fv) < 3:
                        continue
                    face_v.extend(fv)
                    face_len.append(len(fv))
                    if want_vn:
                        face_vn.extend(fn)
                    if keep_raw:
                        face_vt.extend(ft)
                    nf += 1

                elif tag == 'vn':
                    if len(parts) < 4:
                        continue
                    n_flat.extend(parts[1:4])
                    n_lines.append(line_counter)
                    nvn += 1
                    if len(n_flat) >= FLUSH_EVERY:
                        _flush(n_flat, n_chunks, n_lines)

                elif tag == 'vt':
                    if len(parts) >= 3:
                        nvt += 1        # las coords de textura no se dibujan: solo se cuentan
                        if keep_raw:
                            tex_list.append([float(parts[1]), float(parts[2]),
                                             float(parts[3]) if len(parts) > 3 else 0.0])

        _flush(v_flat, v_chunks, v_lines)
        _flush(n_flat, n_chunks, n_lines)
    except ObjParseError:
        raise                       # ya trae la línea exacta
    except Exception as e:
        raise ValueError(f"LINE {line_counter}: {e}") from e

    if nv == 0:
        raise ValueError("the file has no vertices")

    vertices = np.concatenate(v_chunks)
    normals = np.concatenate(n_chunks) if n_chunks else np.zeros((0, 3), dtype=np.float32)

    if nf == 0:
        edges = np.zeros((0, 2), dtype=np.uint32)
        tri_v = np.zeros(0, dtype=np.uint32) if need_faces else None
        tri_vn = np.zeros(0, dtype=np.int32) if need_faces else None
        mesh = Mesh(vertices, edges, normals, tri_v, tri_vn, nv, 0, 0, nvt, nvn)
        if keep_raw:
            mesh.poly_v = np.zeros(0, dtype=np.int64)
            mesh.poly_vt = np.zeros(0, dtype=np.int64)
            mesh.poly_vn = np.zeros(0, dtype=np.int64)
            mesh.poly_len = np.zeros(0, dtype=np.int64)
            mesh.tex_coords = tex_list
        return mesh

    V = np.frombuffer(face_v, dtype=np.intc).astype(np.int64)
    flen = np.frombuffer(face_len, dtype=np.intc).astype(np.int64)

    if V.min() < 0 or V.max() >= nv:
        raise ValueError("a face references a vertex that does not exist")

    starts = np.cumsum(flen) - flen
    total = V.size

    # ---- aristas (borde de cada polígono original), únicas y ordenadas ----
    rep_starts = np.repeat(starts, flen)
    rep_len = np.repeat(flen, flen)
    idx = np.arange(total, dtype=np.int64)
    nxt = np.where(idx - rep_starts == rep_len - 1, rep_starts, idx + 1)
    a = V
    b = V[nxt]
    lo = np.minimum(a, b)
    hi = np.maximum(a, b)
    keys = np.unique(lo * nv + hi)
    edges = np.stack([keys // nv, keys % nv], axis=1).astype(np.uint32)
    del rep_starts, rep_len, idx, nxt, a, b, lo, hi, keys

    # ---- triangulación en abanico (0, i, i+1) para el relleno ----
    tri_v = tri_vn = None
    if need_faces:
        ntri = flen - 2
        tcount = int(ntri.sum())
        tface = np.repeat(np.arange(nf, dtype=np.int64), ntri)
        tstart = np.cumsum(ntri) - ntri
        local = np.arange(tcount, dtype=np.int64) - np.repeat(tstart, ntri) + 1
        base = starts[tface]
        sel = np.stack([base, base + local, base + local + 1], axis=1).ravel()
        tri_v = V[sel].astype(np.uint32)

        VN = np.frombuffer(face_vn, dtype=np.intc).astype(np.int32)
        VN[(VN < 0) | (VN >= nvn)] = -1
        tri_vn = VN[sel]

    mesh = Mesh(vertices, edges, normals, tri_v, tri_vn, nv, nf, edges.shape[0], nvt, nvn)
    mesh.last_poly_verts = int(flen[-1])
    if keep_raw:
        mesh.poly_v = V
        mesh.poly_len = flen
        mesh.poly_vn = np.frombuffer(face_vn, dtype=np.intc).astype(np.int64)
        mesh.poly_vn[(mesh.poly_vn < 0) | (mesh.poly_vn >= nvn)] = -1
        mesh.poly_vt = np.frombuffer(face_vt, dtype=np.intc).astype(np.int64)
        mesh.poly_vt[(mesh.poly_vt < 0) | (mesh.poly_vt >= nvt)] = -1
        mesh.tex_coords = tex_list
    return mesh


def read_cache(filename, need_faces):
    cp = filename + CACHE_SUFFIX
    try:
        if not os.path.exists(cp) or os.path.getmtime(cp) < os.path.getmtime(filename):
            return None
        with np.load(cp) as d:
            if int(d['version']) != CACHE_VERSION:
                return None
            if need_faces and not bool(d['has_faces']):
                return None
            counts = d['counts']
            tri_v = d['tri_v'] if bool(d['has_faces']) else None
            tri_vn = d['tri_vn'] if bool(d['has_faces']) else None
            edges = d['edges']
            return Mesh(d['vertices'], edges, d['normals'], tri_v, tri_vn,
                        int(counts[0]), int(counts[1]), edges.shape[0], int(counts[2]), int(counts[3]))
    except Exception as e:
        print(Fore.YELLOW + f"Cache ignored ({e})" + Style.RESET_ALL)
        return None


def write_cache(filename, mesh):
    cp = filename + CACHE_SUFFIX
    has_faces = mesh.tri_v is not None
    try:
        np.savez(cp,
                 version=np.array(CACHE_VERSION),
                 has_faces=np.array(has_faces),
                 counts=np.array([mesh.num_verts, mesh.num_faces, mesh.num_vt, mesh.num_vn], dtype=np.int64),
                 vertices=mesh.vertices,
                 edges=mesh.edges,
                 normals=mesh.normals,
                 tri_v=mesh.tri_v if has_faces else np.zeros(0, dtype=np.uint32),
                 tri_vn=mesh.tri_vn if has_faces else np.zeros(0, dtype=np.int32))
    except Exception as e:
        print(Fore.YELLOW + f"Could not write cache: {e}" + Style.RESET_ALL)


def load_obj(filename, args):
    """Devuelve un Mesh, o None si hubo error de lectura."""
    # getattr: así también funciona con scripts externos cuyo parser no define estas opciones
    use_cache = getattr(args, 'use_cache', False)
    keep_raw = getattr(args, 'keep_raw', False)
    if keep_raw:
        use_cache = False       # la caché no guarda la estructura original de polígonos

    try:
        mesh = None
        if use_cache:
            mesh = read_cache(filename, args.fill_object)
            if mesh is not None:
                print("Loaded from cache")

        if mesh is None:
            # con caché se parsean también las caras, para que el .npz sirva con y sin -fill
            mesh = parse_obj(filename, args.fill_object or use_cache, keep_raw)
            if use_cache:
                write_cache(filename, mesh)

        # CENTERING (se aplica después de la caché, que guarda los datos originales)
        if args.enable_centering and mesh.vertices.shape[0] > 0:
            center = ((mesh.vertices.min(axis=0).astype(np.float64) +
                       mesh.vertices.max(axis=0)) / 2.0).astype(np.float32)
            mesh.vertices -= center

        if not args.fill_object:
            mesh.tri_v = None
            mesh.tri_vn = None

        return mesh

    except Exception as e:
        print(f"FILE ERROR {str(e)}")
        return None


def load_obj_legacy(filename, args):
    """Compatibilidad con la API antigua de load_obj (herramientas como test_script.py).

    Devuelve la misma tupla de 12 elementos que antes:
    (vertices, edges, num_verts, num_triangles, num_edges, faces,
     polygon_verts, load_error, tex_coords, normals, num_vt, num_vn)
    No usar en el visor: construye listas de Python y es lento con modelos grandes.
    """
    legacy_args = argparse.Namespace(**{**vars(args), 'keep_raw': True, 'use_cache': False})
    mesh = load_obj(filename, legacy_args)
    if mesh is None:
        return [], None, 0, 0, 0, [], 0, True, [], [], 0, 0

    vertices = mesh.vertices.tolist()
    edges = [tuple(e) for e in mesh.edges.tolist()]
    normals = mesh.normals.tolist()

    faces = []
    if args.fill_object and mesh.poly_len is not None:
        pv, pvt, pvn = mesh.poly_v.tolist(), mesh.poly_vt.tolist(), mesh.poly_vn.tolist()
        pos = 0
        for n in mesh.poly_len.tolist():
            faces.append([{'v': pv[i],
                           'vt': pvt[i] if pvt[i] >= 0 else None,
                           'vn': pvn[i] if pvn[i] >= 0 else None}
                          for i in range(pos, pos + n)])
            pos += n

    return (vertices, edges, mesh.num_verts, mesh.num_faces, mesh.num_edges, faces,
            mesh.last_poly_verts, False, mesh.tex_coords or [], normals,
            mesh.num_vt, mesh.num_vn)


# ----------------------------------------------------------------------------
# Texto en pantalla
# ----------------------------------------------------------------------------
_text_cache: dict = {}

def drawText(f, x, y, text, c, bgc):
    if text not in _text_cache:
        if len(_text_cache) > 256:          # evita crecer sin límite al hacer zoom ("Scale: ...")
            _text_cache.clear()
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
    print("  - 'H' Key: Toggle the visibility of on-screen information")
    print("  - ESC Key: Exit the program")

    print("\n----------------------------------------------------")


# ----------------------------------------------------------------------------
# Cuaterniones
# ----------------------------------------------------------------------------
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


def create_rotation_quaternion(angle, x, y, z):
    half_angle = math.radians(angle) / 2.0
    sin_half_angle = math.sin(half_angle)
    return Quaternion(math.cos(half_angle), x * sin_half_angle, y * sin_half_angle, z * sin_half_angle)


# ----------------------------------------------------------------------------
# Vistas
# ----------------------------------------------------------------------------
def setup_view_ortho(display):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()

    aspect_ratio = display[0] / display[1]
    ortho_size = 10
    # (near/far reconstruidos: usa los tuyos si eran distintos)
    glOrtho(-ortho_size * 0.5 * aspect_ratio, ortho_size * 0.5 * aspect_ratio,
            -ortho_size * 0.5, ortho_size * 0.5, 0.01, 1000.0)

    glMatrixMode(GL_MODELVIEW)

def text_pos(h, p):
    inc_total = (h - 600)
    h_pos = p + inc_total
    return h_pos

def setup_view_perspective(display):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(50, (display[0] / display[1]), 0.01, 1000.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glTranslatef(0.0, 0.0, -10.0)


# ----------------------------------------------------------------------------
# Modelo en GPU (VBO / EBO)
# ----------------------------------------------------------------------------
def _upload(target, data):
    data = np.ascontiguousarray(data)
    buf = glGenBuffers(1)
    glBindBuffer(target, buf)
    glBufferData(target, data.nbytes, data, GL_STATIC_DRAW)
    return buf


class GLModel:
    """Sube la geometría a la GPU una sola vez y la dibuja con glDrawElements."""

    def __init__(self, mesh, fill):
        self.buffers = []

        # --- aristas ---
        self.vbo_pos = _upload(GL_ARRAY_BUFFER, mesh.vertices.astype(np.float32, copy=False))
        self.ebo_lines = _upload(GL_ELEMENT_ARRAY_BUFFER, mesh.edges.ravel().astype(np.uint32, copy=False))
        self.n_lines = int(mesh.edges.size)
        self.buffers += [self.vbo_pos, self.ebo_lines]

        # --- relleno ---
        self.n_fill = 0
        self.vbo_fill = self.vbo_pos
        self.vbo_norm = None
        self.ebo_fill = None

        if fill and mesh.tri_v is not None and mesh.tri_v.size > 0:
            tri_v, tri_vn = mesh.tri_v, mesh.tri_vn

            if mesh.num_vn > 0:
                # En OBJ v y vn se indexan por separado; OpenGL necesita un único índice.
                # Se crea un vértice por cada pareja (v, vn) distinta.
                m = mesh.num_vn + 1
                key = tri_v.astype(np.int64) * m + (tri_vn.astype(np.int64) + 1)
                uniq, inv = np.unique(key, return_inverse=True)
                uv = uniq // m
                un = (uniq % m) - 1
                pos = mesh.vertices[uv].astype(np.float32)
                nrm = np.zeros((uniq.size, 3), dtype=np.float32)
                nrm[:, 2] = 1.0
                ok = un >= 0
                nrm[ok] = mesh.normals[un[ok]]
                idx = inv.reshape(-1).astype(np.uint32)

                self.vbo_fill = _upload(GL_ARRAY_BUFFER, pos)
                self.vbo_norm = _upload(GL_ARRAY_BUFFER, nrm)
                self.buffers += [self.vbo_fill, self.vbo_norm]
            else:
                idx = tri_v.astype(np.uint32, copy=False)

            self.ebo_fill = _upload(GL_ELEMENT_ARRAY_BUFFER, idx)
            self.n_fill = int(idx.size)
            self.buffers.append(self.ebo_fill)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

        # los datos ya viven en la GPU: se libera la copia de relleno en RAM
        mesh.tri_v = None
        mesh.tri_vn = None

    def draw(self, edge_color, line_width, lighting, factor, units):
        glEnableClientState(GL_VERTEX_ARRAY)

        # aristas (siempre sin iluminación, con el color de línea)
        glDisable(GL_LIGHTING)
        glColor3f(*edge_color)
        glLineWidth(line_width)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_pos)
        glVertexPointer(3, GL_FLOAT, 0, None)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo_lines)
        glDrawElements(GL_LINES, self.n_lines, GL_UNSIGNED_INT, None)

        # relleno
        if self.n_fill:
            glEnable(GL_POLYGON_OFFSET_FILL)
            glPolygonOffset(factor, units)

            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_fill)
            glVertexPointer(3, GL_FLOAT, 0, None)

            if lighting and self.vbo_norm is not None:
                glEnable(GL_LIGHTING)
                glEnable(GL_LIGHT0)
                glColor3f(1.0, 1.0, 1.0)
                glEnableClientState(GL_NORMAL_ARRAY)
                glBindBuffer(GL_ARRAY_BUFFER, self.vbo_norm)
                glNormalPointer(GL_FLOAT, 0, None)
            else:
                glColor3f(0.0, 0.5, 0.0)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo_fill)
            glDrawElements(GL_TRIANGLES, self.n_fill, GL_UNSIGNED_INT, None)

            glDisableClientState(GL_NORMAL_ARRAY)
            glDisable(GL_LIGHTING)
            glDisable(GL_LIGHT0)
            glDisable(GL_POLYGON_OFFSET_FILL)

        glDisableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    def delete(self):
        for b in self.buffers:
            glDeleteBuffers(1, [b])
        self.buffers = []


def create_window(display, samples):
    """Crea la ventana con antialiasing; si el driver no lo soporta, reintenta sin él."""
    try:
        if samples > 0:
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, samples)
        pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
        return samples > 0
    except pygame.error:
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 0)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 0)
        pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
        return False


# ----------------------------------------------------------------------------
# Ventana principal
# ----------------------------------------------------------------------------
def window(args):
    try:
        path = args.load_object
        model_name = os.path.basename(path)

        t0 = time.perf_counter()
        mesh = load_obj(path, args)

        if mesh is not None:
            print(f"Model loaded in {time.perf_counter() - t0:.2f}s")
            show_controls()
            pygame.init()

            text_bg = tuple(rgb_t[args.bg_color])

            text_pos1 = text_pos(args.window_height, 570)
            text_pos2 = text_pos(args.window_height, 550)
            text_pos3 = text_pos(args.window_height, 530)
            text_pos4 = text_pos(args.window_height, 510)
            text_pos5 = text_pos(args.window_height, 490)
            text_pos6 = text_pos(args.window_height, 470)
            text_pos7 = text_pos(args.window_height, 450)
            text_pos8 = text_pos(args.window_height, 430)
            text_pos9 = text_pos(args.window_height, 410)
            vnvt = [text_pos7, text_pos8, text_pos9]

            display = (args.window_width, args.window_height)

            multisampled = create_window(display, args.antialiasing)

            if multisampled:
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

            if mesh.num_vn > 0 and args.fill_object:
                # Preparar iluminación básica (se activa/desactiva con 'U')
                glLightfv(GL_LIGHT0, GL_POSITION, (0.0, 0.0, 1.0, 0.0))
                glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.6, 0.85, 0.6, 1.0))
                glLightfv(GL_LIGHT0, GL_AMBIENT, (0.15, 0.15, 0.15, 1.0))
                glEnable(GL_COLOR_MATERIAL)
                glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
                glEnable(GL_NORMALIZE)      # el glScalef (p. ej. -scl 0.001) encoge las normales

            has_normals = mesh.num_vn > 0
            use_normals = False  # se activa con la tecla 'U'
            factor = args.factor
            units = args.units

            scale = args.scale
            hide_data = False
            rotating = False

            if args.bg_color == 'white':
                edge_color = (0.0, 0.0, 0.0)
                green_val = 100
            else:
                edge_color = (1.0, 1.0, 1.0)
                green_val = 255

            # CONSTRUCCIÓN DEL MODELO EN GPU
            model = GLModel(mesh, args.fill_object)

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
                            else:
                                print(Fore.YELLOW + f"No 'vn' data on file '{model_name}' (or -fill not enabled)." + Style.RESET_ALL)

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
                        zoom_factor = 1.08 if event.y > 0 else (1 / 1.08 if event.y < 0 else 1.0)
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
                    scale -= args.zoom_rate * (dt / (1 / 60))
                if key[pygame.K_x]:
                    scale += args.zoom_rate * (dt / (1 / 60))
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
                model.draw(edge_color, args.line_width, use_normals, factor, units)

                glPopMatrix()

                if not hide_data:
                    fg = (0, green_val, 0)
                    drawText(font, 20, text_pos1, f'Model: {model_name}', fg, text_bg)
                    drawText(font, 20, text_pos2, f'Scale: {round(scale, 6)}', fg, text_bg)
                    view_mode = "Orthographic" if is_ortho else "Perspective"
                    drawText(font, 20, text_pos3, f'View: {view_mode}', fg, text_bg)
                    drawText(font, 20, text_pos4, f'Num Verts: {mesh.num_verts}', fg, text_bg)
                    drawText(font, 20, text_pos5, f'Num Faces: {mesh.num_faces}', fg, text_bg)
                    drawText(font, 20, text_pos6, f'Num Edges: {mesh.num_edges}', fg, text_bg)
                    slot = 0
                    if mesh.num_vt > 0:
                        drawText(font, 20, vnvt[slot], f'Num VT (tex coords): {mesh.num_vt}', fg, text_bg)
                        slot += 1
                    if mesh.num_vn > 0:
                        drawText(font, 20, vnvt[slot], f'Num VN (normals): {mesh.num_vn}', fg, text_bg)
                        slot += 1
                        drawText(font, 20, vnvt[slot], f'Lighting: {"ON" if use_normals else "OFF"}', fg, text_bg)

                pygame.display.flip()
                clock.tick(args.max_fps)

            model.delete()
            pygame.quit()
        else:
            print(Fore.RED + Style.BRIGHT + "FILE ERROR" + Fore.RESET + Style.RESET_ALL)
            print("terminated")

    except Exception as e:
        print(Fore.RED + Style.BRIGHT + "UNEXPECTED ERROR: " + e.__str__() + Fore.RESET + Style.RESET_ALL)


def main():
    # Los valores por defecto de width/height/rspd/tspd y los textos de ayuda están
    # reconstruidos (el pegado original llegaba cortado): pon aquí los tuyos.
    parser = argparse.ArgumentParser(prog="pymeshgl", conflict_handler='resolve',
                                     description="Show obj models",
                                     epilog="REPO: https://github.com/antonioam8",
                                     allow_abbrev=False)
    parser.add_argument('-load', '--load_object', required=True, type=check_source_ext, help="Path to the .obj model")
    parser.add_argument('-width', '--window_width', type=check_width_value, default=800, help="Window width (800-1600)")
    parser.add_argument('-height', '--window_height', type=check_height_value, default=600, help="Window height (600-900)")
    parser.add_argument('-bg', '--bg_color', type=check_color, default='black', help="Background color: blue, gray, black, white")
    parser.add_argument('-lw', '--line_width', type=check_lw, default=1.0, help="Line width (0.1-10.0)")
    parser.add_argument('-fill', '--fill_object', action='store_true', help="Add solid faces to the model")
    parser.add_argument('-scl', '--scale', type=check_positive, default=1.0, help="Initial scale")
    parser.add_argument('-zr', '--zoom_rate', type=check_positive, default=0.05, help="Zoom rate for the Z/X keys")
    parser.add_argument('-ec', '--enable_centering', action='store_true', help="Enable model centering")
    parser.add_argument('-rspd', '--rotation_speed', type=check_positive, default=90.0, help="Rotation speed (degrees per second)")
    parser.add_argument('-tspd', '--translation_speed', type=check_positive, default=5.0, help="Translation speed (units per second)")
    parser.add_argument('-f', '--factor', type=float, default=0.0, help="Slope Scale Factor for glPolygonOffset (needs -fill)")
    parser.add_argument('-u', '--units', type=float, default=0.0, help="Minimum Resolvable Depth Units for glPolygonOffset (needs -fill)")
    # nuevos
    parser.add_argument('-cache', '--use_cache', action='store_true',
                        help="Save/load the parsed model in a .pymeshgl.npz file next to the .obj")
    parser.add_argument('-aa', '--antialiasing', type=int, choices=[0, 2, 4, 6, 8], default=6,
                        help="MSAA samples (0 = off). Lower it for very dense models")
    parser.add_argument('-fps', '--max_fps', type=int, default=120, help="Frame rate cap")

    args = parser.parse_args()
    if (args.factor != 0.0 or args.units != 0.0) and not args.fill_object:
        parser.error("Arguments '-f/--factor' and '-u/--units' only can be used with '-fill'")

    window(args)

if __name__ == "__main__":
    main()
