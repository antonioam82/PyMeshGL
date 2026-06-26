from setuptools import setup

setup(
    name="pymeshgl",
    version="1.0.0",
    description="Visor 3D interactivo de modelos OBJ con OpenGL y rotacion por cuaterniones",
    py_modules=["PyMeshGL"],
    install_requires=[
        "pygame",
        "PyOpenGL",
        "numpy",
        "colorama",
    ],
    entry_points={
        "console_scripts": [
            "pymeshgl=PyMeshGL:main",
        ],
    },
    python_requires=">=3.9",
)
