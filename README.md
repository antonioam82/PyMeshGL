# PyMeshGL
Visor 3D interactivo de modelos OBJ con OpenGL.

PyMeshGL es un visor 3D ligero para archivos .obj escrito en Python con Pygame y PyOpenGL. 
Permite cargar modelos y explorarlos en tiempo real con rotación suave basada en cuaterniones, 
vistas predefinidas (frontal, cenital, lateral...), proyección ortográfica o en perspectiva, 
zoom, paneo con el mouse y renderizado en wireframe o sólido.

## Instalación

### Opción 1: comando global (recomendado)

```bash
git clone https://github.com/TU-USUARIO/PyMeshGL.git
cd PyMeshGL
pip install -e .
```

Esto instala las dependencias **y** registra el comando `pymeshgl`, disponible desde cualquier carpeta:

```bash
pymeshgl -load modelo.obj -ec
```

### Opción 2: ejecutar el script directamente

Si no quieres instalar el comando global, solo necesitas las dependencias:

```bash
pip install -r requirements.txt
python PyMeshGL.py -load modelo.obj -ec
```

| | ¿Obligatorio? | Para qué sirve |
|---|---|---|
| `pip install -r requirements.txt` | ✅ Sí | Instala las librerías que el script necesita para funcionar |
| `pip install -e .` | ❌ No, es comodidad | Instala las dependencias y además crea el comando global `pymeshgl`, para no usar `python` ni rutas |

## Modo de uso

```
pymeshgl -load <archivo.obj> [opciones]
```

| Opción | Descripción | Por defecto |
|---|---|---|
| `-load`, `--load_object` | Modelo `.obj` a cargar (obligatorio) | — |
| `-width`, `--window_width` | Ancho de ventana (800-1600) | 800 |
| `-height`, `--window_height` | Alto de ventana (600-900) | 600 |
| `-bg`, `--bg_color` | Color de fondo: `blue`, `gray`, `black`, `white` | black |
| `-lw`, `--line_width` | Grosor de línea (0.1-10.0) | 1.0 |
| `-fill`, `--fill_object` | Rellena el modelo con color sólido | desactivado |
| `-scl`, `--scale` | Escala inicial del objeto | 1.0 |
| `-zr`, `--zoom_rate` | Velocidad de zoom | 0.05 |
| `-ec`, `--enable_centering` | Centra automáticamente el modelo | desactivado |
| `-rspd`, `--rotation_speed` | Velocidad de rotación (grados/seg) | 90.0 |
| `-tspd`, `--translation_speed` | Velocidad de traslación | 2.0 |

### Ejemplo

```bash
pymeshgl -load satelite.obj -ec -scl 0.001 -zr 0.0001 -width 1500 -height 770 -lw 0.3
```

### Controles

**Movimiento (flechas):** rotan la escena arriba/abajo/izquierda/derecha.

**Traslación:** `A` izquierda · `S` derecha · `D` arriba · `F` abajo

**Rotación:** `R` resetea vista · `M` / `N` rotan sobre el eje Z

**Vistas predefinidas:** `T` cenital · `B` inferior · `J` derecha · `L` izquierda · `G` frontal · `K` posterior

**Proyección:** `P` alterna entre ortográfica y perspectiva

**Zoom:** `Z` / `X` o rueda del ratón

**Arrastre con ratón:** botón izquierdo mueve la escena, botón derecho la rota

**Otros:** `H` oculta/muestra la información en pantalla · `ESC` sale

