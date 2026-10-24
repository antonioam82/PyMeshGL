#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Permite ejecutar este script directamente (sin instalar el paquete con
# 'pip install -e .') añadiendo la carpeta donde vive PyMeshGL.py al
# sys.path. test_script.py está en la raíz del repo, junto a PyMeshGL.py,
# así que basta con 'parent' (no 'parent.parent'). Si el paquete ya está
# instalado, este bloque ni se activa (el import normal tiene prioridad).
try:
    from PyMeshGL import load_obj_legacy, check_source_ext
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from PyMeshGL import load_obj_legacy, check_source_ext

from itertools import islice
from collections import deque
import argparse

def check_item(item):
    items = ['faces','edges','vertices','tex_coords',
             'normals','none']
    if item not in items:
        raise argparse.ArgumentTypeError("Item must be 'faces', 'edges', 'vertices', 'tex_coords', 'normals' or 'none'")
    return item

def main():
    parser = argparse.ArgumentParser(prog="test_script", conflict_handler='resolve',
                                     description='''PyMeshGL diagnostic tool: loads an OBJ model
                                     (the same parser used by PyMeshGL.py) and prints its counters and,
                                     optionally, its vertices, edges, faces, texture coordinates (vt) and
                                     normals (vn).
                                     Handy for quickly checking that a model is loaded correctly.''')
    parser.add_argument('-load','--load_object',required=True,type=check_source_ext,help='Path to the .obj model')
    parser.add_argument('-item','--show_item',required=True,type=check_item,help="Item to print: 'faces', 'edges', 'vertices', 'tex_coords', 'normals' or 'none'")
    parser.add_argument('-fill','--fill_object',action='store_true',help='Use color/fill mode when loading (keeps the faces in memory)')
    parser.add_argument('-ec','--enable_centering',action='store_true', help='Center the model before printing it')
    parser.add_argument('-nvl','--num_verts_list',action='store_true',help='List the distinct vertex counts per face (implies -fill).')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-hd', '--head', type=int, default=None,help='Show first N items')
    group.add_argument('-t', '--tail', type=int, default=None,help='Show last N items')

    args = parser.parse_args()
    if args.show_item == 'faces' or args.num_verts_list:
        args.fill_object = True
    try:
        filename = args.load_object
        # load_obj_legacy(filename, args) -- misma tupla que devolvía el load_obj antiguo;
        # lee fill internamente como args.fill_object
        v, e, nv, nt, ne, f, pv, le, tc, n, nvt, nvn = load_obj_legacy(filename, args)

        if args.num_verts_list:
            npv = sorted({len(face) for face in f})
            print(f"\nNUMBER OF DISTINCT VERTEX COUNTS PER FACE: {len(npv)}")
            print(f"POLYGON TYPES FOUND: {npv}")

        item_ = args.show_item
        long = abs(30-(len(filename)))

        print(f"\n{filename}{'-'*long}")
        print(f"NUM VERTS: {nv}")
        print(f"NUM FACES: {nt}")
        print(f"NUM EDGES: {ne}")
        print(f"NUM VECTS: {nvt}")
        print(f"NUM NORMS: {nvn}")
        print(f"POL VERTS: {pv}")
        print(f"LDL ERROR: {le}")

        print('-'*30)
        if item_ != 'none':
            if item_ == 'vertices':
               if args.head and args.head < nv:
                   print(f'VERTICES:\n{v[:args.head]}','...')
               elif args.tail and args.tail < nv:
                   print(f'VERTICES:\n... {v[-args.tail:]}')
               else:
                   print(f'VERTICES:\n{v}')
            elif item_ == 'edges':
                if args.head and args.head < ne:
                   print(f'EDGES:\n{list(islice(e,args.head))}','...')
                elif args.tail and args.tail < ne:
                   last_values = list(deque(e, maxlen=args.tail))
                   print(f'EDGES:\n... {last_values}')
                else:
                    print(f'EDGES:\n{e}')
            elif item_ == 'faces':
                if args.head and args.head < nt:
                    print(f'FACES:\n{f[:args.head]}','...')
                elif args.tail and args.tail < nt:
                    print(f'FACES:\n... {f[-args.tail:]}')
                else:
                    print(f'FACES:\n{f}')
            elif item_ == 'tex_coords':
                if args.head and args.head < nvt:
                    print(f'TEXTURE COORDS:\n{tc[:args.head]}','...')
                elif args.tail and args.tail < nvt:
                    print(f'TEXTURE COORDS:\n... {tc[-args.tail:]}')
                else:
                    print(f'TEXTURE COORDS:\n{tc}')
            elif item_ == 'normals':
                if args.head and args.head < nvn:
                    print(f'NORMALS:\n{n[:args.head]}','...')
                elif args.tail and args.tail < nvn:
                    print(f'NORMALS:\n... {n[-args.tail:]}')
                else:
                    print(f'NORMALS:\n{n}')

    except Exception as e:
        print(f"UNEXPECTED ERROR: {str(e)}.")

if __name__ =="__main__":
    main()
