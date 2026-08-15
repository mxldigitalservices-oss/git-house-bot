"""
Búsqueda de inventario para el bot — todo resuelto con consultas SQL
directas contra la tabla `properties` (sin llamar a ningún servicio
externo). Las zonas conocidas se leen dinámicamente de la propia tabla,
así que al agregar propiedades en sectores nuevos, el bot las reconoce
automáticamente sin tocar código.
"""
import math
import re
import unicodedata

from sqlalchemy.orm import Session

from app.models import Property

PALABRAS_ALQUILER = ("alquilar", "alquiler", "rentar", "renta")
PALABRAS_VENTA = ("vender", "venta", "comprar", "compra")


def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", texto)


def _zonas_conocidas(db: Session) -> list[str]:
    """Lee las zonas ya cargadas en la base — crece sola con el inventario."""
    filas = db.query(Property.zona).distinct().all()
    return [z[0] for z in filas]


def _zona_mencionada(zona: str, texto_normalizado: str) -> bool:
    """
    Coincidencia por mayoría de palabras: "alma rosa" sí debe calzar con
    la zona "Alma Rosa Primera" (2 de 3 palabras presentes), pero una
    sola palabra suelta y genérica no basta para evitar falsos positivos.
    """
    zona_tokens = _normalizar(zona).split()
    if not zona_tokens:
        return False
    texto_tokens = set(texto_normalizado.split())
    coincidencias = sum(1 for t in zona_tokens if t in texto_tokens)
    necesarias = math.ceil(len(zona_tokens) * 0.66)
    return coincidencias >= necesarias


def buscar_propiedades(db: Session, mensaje_usuario: str, limite: int = 5) -> list[Property]:
    """
    Devuelve propiedades disponibles que calzan con lo que el usuario
    escribió. Solo dispara si se reconoce una ZONA concreta del
    inventario — así una pregunta de política como "¿cómo publico una
    propiedad?" no se confunde con una búsqueda de inventario.
    """
    texto = _normalizar(mensaje_usuario)

    zona_detectada = None
    for zona in _zonas_conocidas(db):
        if _zona_mencionada(zona, texto):
            zona_detectada = zona
            break

    if zona_detectada is None:
        return []

    query = db.query(Property).filter(
        Property.estado == "disponible", Property.zona == zona_detectada
    )

    if any(p in texto for p in PALABRAS_ALQUILER):
        query = query.filter(Property.tipo == "alquiler")
    elif any(p in texto for p in PALABRAS_VENTA):
        query = query.filter(Property.tipo == "venta")

    return query.order_by(Property.actualizado_en.desc()).limit(limite).all()


def formatear_propiedades(propiedades: list[Property]) -> str:
    """Arma un mensaje de WhatsApp legible a partir de las filas encontradas."""
    if not propiedades:
        return ""

    partes: list[str] = []
    for p in propiedades:
        linea = f"🏠 *{p.titulo}* — {p.zona}\n"
        linea += f"{'En alquiler' if p.tipo == 'alquiler' else 'En venta'} — RD$ {p.precio:,.0f}"
        detalles = []
        if p.habitaciones:
            detalles.append(f"{p.habitaciones} hab.")
        if p.banos:
            detalles.append(f"{p.banos} baños")
        if p.area_m2:
            detalles.append(f"{p.area_m2:.0f} m²")
        if detalles:
            linea += "\n" + " · ".join(detalles)
        if p.descripcion:
            linea += "\n" + p.descripcion[:160]
        partes.append(linea)

    return "\n\n".join(partes)
