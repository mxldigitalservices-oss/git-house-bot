"""
Sistema de handover ("modo humano") por número de teléfono.

Cuando un número pide hablar con un agente humano, el bot deja de
responder SOLO para ese número — el estado vive en la tabla
chat_handovers, indexada por teléfono, así que no afecta a ningún otro
usuario que siga escribiéndole al mismo bot en paralelo.
"""
import re
import unicodedata

from sqlalchemy.orm import Session

from app.models import ChatHandover
from app.utils import normalizar_telefono

# Frases/palabras que disparan el handover. Se comparan contra el texto
# ya normalizado (sin acentos, en minúscula), así que aquí van también
# sin acentos.
PALABRAS_CLAVE_HUMANO: set[str] = {
    "agente",
    "agente humano",
    "humano",
    "representante",
    "asesor",
    "persona real",
    "hablar con alguien",
    "hablar con una persona",
    "hablar con un humano",
    "hablar con un agente",
    "quiero un agente",
    "necesito un agente",
    "atencion al cliente",
    "servicio al cliente",
    "operador",
}

MENSAJE_CORTESIA_HANDOVER = (
    "Espere unos minutos, en breve le atenderemos. "
    "Un miembro de nuestro equipo continuará esta conversación."
)


def _normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto


def solicita_agente_humano(mensaje: str) -> bool:
    """True si el mensaje contiene alguna palabra/frase clave de handover."""
    texto = _normalizar_texto(mensaje)
    return any(clave in texto for clave in PALABRAS_CLAVE_HUMANO)


def obtener_o_crear_estado(db: Session, phone: str) -> ChatHandover:
    phone_norm = normalizar_telefono(phone)
    estado = db.query(ChatHandover).filter_by(phone=phone_norm).one_or_none()
    if estado is None:
        estado = ChatHandover(phone=phone_norm, bot_activo=True)
        db.add(estado)
        db.commit()
        db.refresh(estado)
    return estado


def desactivar_bot(db: Session, phone: str, motivo: str | None = None) -> ChatHandover:
    """Pasa el número a modo humano (el bot deja de responderle)."""
    estado = obtener_o_crear_estado(db, phone)
    estado.bot_activo = False
    estado.motivo = motivo
    db.commit()
    db.refresh(estado)
    return estado


def activar_bot(db: Session, phone: str) -> ChatHandover:
    """Devuelve el número a respuestas automáticas normales."""
    estado = obtener_o_crear_estado(db, phone)
    estado.bot_activo = True
    estado.motivo = None
    db.commit()
    db.refresh(estado)
    return estado
