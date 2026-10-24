# PyMeshGL
Visor 3D interactivo de modelos OBJ con OpenGL.

PyMeshGL es un visor 3D ligero para archivos .obj escrito en Python con Pygame y PyOpenGL.
Permite cargar modelos y explorarlos en tiempo real con rotación suave basada en cuaterniones,
vistas predefinidas (frontal, cenital, lateral...), proyección ortográfica o en perspectiva,
zoom, paneo con el ratón y renderizado en wireframe o sólido, con iluminación opcional a partir
de las normales del modelo.

## Características

- Lectura de posiciones (`v`), coordenadas de textura (`vt`) y normales (`vn`), con soporte para
  los formatos de cara `v`, `v/vt`, `v//vn` y `v/vt/vn` (incluidos los índices negativos).
- Mallas con caras de distinto número de lados (triángulos, cuadriláteros y n-gonos mezclados).
- Geometría subida a la GPU una sola vez (VBO/EBO) y lectura del `.obj` con NumPy, pensado para
  modelos grandes.
- Iluminación basada en las normales del modelo, activable en tiempo real con la tecla `U`.
- Caché opcional del modelo ya procesado para abrir más rápido los archivos pesados.
- Herramienta de diagnóstico `test_script` para inspeccionar lo que se lee de un `.obj` sin abrir ventana.

## Instalación

### Opción 1: comandos globales (recomendado)

```bash
git clone https://github.com/antonioam82/PyMeshGL.git
cd PyMeshGL
pip install -e .
```

Esto instala las dependencias **y** registra dos comandos, disponibles desde cualquier carpeta:

| Comando | Para qué sirve |
|---|---|
| `pymeshgl` | Abre el visor 3D |
| `test_script` | Imprime por consola los datos que se leen de un `.obj` (ver [más abajo](#test_script-diagnóstico-de-modelos)) |

```bash
pymeshgl -load modelo.obj -ec
```

> Si actualizas el repositorio (`git pull`) y cambia `setup.py`, vuelve a ejecutar `pip install -e .`
> para que se registren los comandos nuevos.

### Opción 2: ejecutar los scripts directamente

Si no quieres instalar los comandos globales, solo necesitas las dependencias:

```bash
pip install -r requirements.txt
python PyMeshGL.py -load modelo.obj -ec
```

| | ¿Obligatorio? | Para qué sirve |
|---|---|---|
| `pip install -r requirements.txt` | ✅ Sí | Instala las librerías que el script necesita para funcionar |
| `pip install -e .` | ❌ No, es comodidad | Instala las dependencias y además crea los comandos globales `pymeshgl` y `test_script`, para no usar `python` ni rutas |

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
| `-zr`, `--zoom_rate` | Velocidad de zoom con las teclas `Z`/`X` | 0.05 |
| `-ec`, `--enable_centering` | Centra automáticamente el modelo | desactivado |
| `-rspd`, `--rotation_speed` | Velocidad de rotación (grados/seg) | 90.0 |
| `-tspd`, `--translation_speed` | Velocidad de traslación (unidades/seg) | 5.0 |
| `-f`, `--factor` | Factor de pendiente de `glPolygonOffset` (requiere `-fill`) | 0.0 |
| `-u`, `--units` | Unidades de profundidad de `glPolygonOffset` (requiere `-fill`) | 0.0 |
| `-cache`, `--use_cache` | Guarda/lee el modelo procesado en un archivo `.pymeshgl.npz` junto al `.obj` | desactivado |
| `-aa`, `--antialiasing` | Muestras MSAA: `0` (desactivado), `2`, `4`, `6` u `8` | 6 |
| `-fps`, `--max_fps` | Límite de fotogramas por segundo | 120 |

### Ejemplos

```bash
# Modelo grande, centrado y a escala reducida
pymeshgl -load satelite.obj -ec -scl 0.001 -zr 0.0001 -width 1500 -height 770 -lw 0.3

# Relleno sólido con iluminación (tecla U) sobre un modelo con normales
pymeshgl -load modelo.obj -ec -fill

# Modelo muy denso: caché para abrirlo más rápido y menos antialiasing para ir más fluido
pymeshgl -load modelo_denso.obj -ec -cache -aa 2
```

### Notas

- **`-f` / `-u`:** ajustan `glPolygonOffset`, que desplaza el relleno ligeramente hacia atrás para que
  las aristas no parpadeen sobre las caras (*z-fighting*). Solo se pueden usar junto con `-fill`;
  si se indican sin él, el programa termina con un error.
- **`-cache`:** la primera vez se procesa el `.obj` y se guarda `<modelo>.obj.pymeshgl.npz` al lado.
  Las siguientes aperturas leen ese archivo (mostrando `Loaded from cache`) siempre que sea más
  reciente que el `.obj`. La caché sirve tanto con `-fill` como sin él, y guarda los datos originales,
  de modo que `-ec` se aplica después de leerla.
- **`-aa`:** si el controlador gráfico no admite el nivel de antialiasing pedido, el visor arranca
  igualmente sin él. Bajar este valor ayuda con modelos muy densos.
- **Relleno:** las caras se triangulan en abanico, así que los polígonos cóncavos pueden rellenarse
  de forma incorrecta. Las aristas (wireframe) no se ven afectadas.

### Controles

**Movimiento (flechas):** rotan la escena arriba/abajo/izquierda/derecha.

**Traslación:** `A` izquierda · `S` derecha · `D` arriba · `F` abajo

**Rotación:** `R` resetea vista · `M` / `N` rotan sobre el eje Z

**Vistas predefinidas:** `T` cenital · `B` inferior · `J` derecha · `L` izquierda · `G` frontal · `K` posterior

**Proyección:** `P` alterna entre ortográfica y perspectiva

**Zoom:** `Z` aleja · `X` acerca · o rueda del ratón

**Arrastre con ratón:** botón izquierdo mueve la escena, botón derecho la rota

**Iluminación:** `U` activa/desactiva la iluminación basada en normales (requiere que el modelo tenga
datos `vn` y que se haya abierto con `-fill`)

**Otros:** `H` oculta/muestra la información en pantalla · `ESC` sale

### Información en pantalla

El panel (se oculta con `H`) muestra el nombre del modelo, la escala, el modo de vista y el número de
vértices, caras y aristas. Si el modelo contiene coordenadas de textura o normales, añade además
`Num VT` y `Num VN`, y el estado de la iluminación (`Lighting: ON/OFF`) cuando hay normales.

## test_script: diagnóstico de modelos

`test_script` carga un `.obj` con el mismo lector que usa `pymeshgl` y vuelca por consola los contadores
del modelo y, opcionalmente, sus datos. No abre ninguna ventana, así que es útil para comprobar
rápidamente que un modelo se está leyendo como se espera.

```
test_script -load <archivo.obj> -item <dato> [opciones]
```

| Opción | Descripción |
|---|---|
| `-load`, `--load_object` | Modelo `.obj` a cargar (obligatorio) |
| `-item`, `--show_item` | Dato a mostrar (obligatorio): `vertices`, `edges`, `faces`, `tex_coords`, `normals` o `none` (solo los contadores) |
| `-fill`, `--fill_object` | Carga también las caras (se activa solo con `-item faces` o `-nvl`) |
| `-ec`, `--enable_centering` | Centra el modelo antes de mostrar los datos |
| `-nvl`, `--num_verts_list` | Muestra los distintos tamaños de cara del modelo (p. ej. `[3, 4]` si mezcla triángulos y cuadriláteros) |
| `-hd`, `--head` | Muestra solo los primeros N elementos |
| `-t`, `--tail` | Muestra solo los últimos N elementos |

`-hd` y `-t` son excluyentes entre sí. Se usa `-hd` y no `-h` porque `-h` queda reservado para la ayuda.

```bash
# Contadores del modelo, sin listar datos
test_script -load modelo.obj -item none

# Primeras 5 caras y tamaños de cara presentes
test_script -load modelo.obj -item faces -hd 5 -nvl

# Últimas 3 normales
test_script -load modelo.obj -item normals -t 3
```

## Licencia

Consulta el archivo [LICENSE](LICENSE).
