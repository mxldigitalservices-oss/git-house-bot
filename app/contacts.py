"""
Reconocimiento de contactos por número de teléfono.

Primera vez que escribe un número: se le pide el nombre (sin exigir
registro previo — cualquiera puede escribir). En su siguiente mensaje,
lo que responda se guarda como su nombre. De ahí en adelante se le
reconoce por el teléfono y se le saluda por nombre cuando corresponde,
sin volver a pedírselo.
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Contact
from app.utils import normalizar_telefono

settings = get_settings()

# Si el usuario responde con frases como "me llamo Pedro" o "soy Ana",
# se recorta el prefijo y solo se guarda el nombre.
_PREFIJOS_NOMBRE = ["me llamo ", "mi nombre es ", "soy "]


def _limpiar_nombre(texto: str) -> str:
    texto = texto.strip()
    texto_lower = texto.lower()
    for prefijo in _PREFIJOS_NOMBRE:
        if texto_lower.startswith(prefijo):
            texto = texto[len(prefijo):].strip()
            break
    # quita signos de puntuación sueltos, conserva letras/acentos/espacios/guiones
    texto = re.sub(r"[^\w\sáéíóúñÁÉÍÓÚÑ'-]", "", texto).strip()
    return texto[:80].title() if texto else "Cliente"


def obtener_o_crear_contacto(db: Session, phone: str) -> tuple[Contact, bool]:
    """Devuelve (contacto, es_nuevo). No requiere registro previo: si el
    número nunca escribió, se crea aquí mismo, de forma dinámica."""
    phone_norm = normalizar_telefono(phone)
    contacto = db.query(Contact).filter_by(phone=phone_norm).one_or_none()
    es_nuevo = False
    if contacto is None:
        contacto = Contact(phone=phone_norm)
        db.add(contacto)
        db.commit()
        db.refresh(contacto)
        es_nuevo = True
    return contacto, es_nuevo


def guardar_nombre(db: Session, contacto: Contact, mensaje_usuario: str) -> Contact:
    """Guarda el nombre recibido, asociado de forma permanente al teléfono."""
    contacto.nombre = _limpiar_nombre(mensaje_usuario)
    db.commit()
    db.refresh(contacto)
    return contacto


def debe_saludar_de_nuevo(contacto: Contact) -> bool:
    """True si pasó suficiente tiempo desde el último mensaje como para
    considerar que es una conversación/sesión nueva."""
    if contacto.ultima_interaccion is None:
        return True
    gap = datetime.now(timezone.utc) - contacto.ultima_interaccion
    return gap > timedelta(hours=settings.saludo_sesion_horas)


def actualizar_ultima_interaccion(db: Session, contacto: Contact) -> None:
    contacto.ultima_interaccion = datetime.now(timezone.utc)
    db.commit()
