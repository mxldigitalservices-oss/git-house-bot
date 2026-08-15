"""
Prueba de humo del normalizador de texto usado por el matcher.
No requiere base de datos: solo valida la función pura _normalizar.
Para probar buscar_mejor_coincidencia end-to-end se necesita una sesión
real de Postgres (ver README para levantar uno local con Docker).
"""
from app.matcher import _normalizar


def test_normalizar_quita_acentos_y_mayusculas():
    assert _normalizar("¿Cómo Vendo Mi CASA?") == "como vendo mi casa"


def test_normalizar_colapsa_espacios():
    assert _normalizar("hola   mundo\n\ncómo estás") == "hola mundo como estas"
