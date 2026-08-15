"""
Router de integración con WhatsApp (vía Green API).

Flujo por mensaje entrante:
  1. n8n hace POST a /whatsapp/webhook con {"phone": "...", "message": "..."}.
  2. Handover: si el bot está en silencio para ese número (un humano ya
     tomó el control), no se responde nada — sin afectar a otros números.
  3. Contacto: cualquier número puede escribir sin registro previo.
       - Primera vez que se ve el número -> se le saluda y se le pide
         el nombre (no se procesa aún como pregunta).
       - Si todavía no tenemos su nombre (ya se le pidió) -> el mensaje
         actual se guarda como su nombre, asociado de forma permanente
         al teléfono, y se le confirma con un saludo.
       - Si ya lo conocemos -> se le reconoce por el teléfono; si pasó
         suficiente tiempo desde su última interacción se le vuelve a
         saludar por nombre, y se continúa directo a la base de
         conocimiento (o al handover si pide un agente humano).
  4. La respuesta se envía vía Green API (sendMessage).
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contacts import (
    actualizar_ultima_interaccion,
    debe_saludar_de_nuevo,
    guardar_nombre,
    obtener_o_crear_contacto,
)
from app.database import get_db
from app.handover import (
    MENSAJE_CORTESIA_HANDOVER,
    desactivar_bot,
    obtener_o_crear_estado,
    solicita_agente_humano,
)
from app.matcher import buscar_mejor_coincidencia
from app.properties import buscar_propiedades, formatear_propiedades
from app.utils import normalizar_telefono

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
settings = get_settings()
logger = logging.getLogger("githouse.whatsapp")

MENSAJE_PEDIR_NOMBRE = (
    "¡Hola! 👋 Bienvenido/a a Git House. "
    "Antes de continuar, ¿me podrías compartir tu nombre?"
)


class WhatsAppMessageIn(BaseModel):
    phone: str = Field(..., description="Número del remitente, ej. 18095551234")
    message: str = Field(..., min_length=1, max_length=2000)


class WhatsAppWebhookOut(BaseModel):
    # success | pidiendo_nombre | nombre_guardado |
    # handover_activado | silenciado_por_handover
    status: str
    phone: str
    mensaje_recibido: str
    respuesta_enviada: str | None = None


def _respuesta_qna(db: Session, mensaje_usuario: str) -> str:
    """Preguntas frecuentes de política/soporte (mismo matcher de /chat/consultar)."""
    candidatos = buscar_mejor_coincidencia(db, mensaje_usuario)

    if not candidatos:
        return (
            "Todavía no tengo información sobre eso. "
            "¿Quieres que te conecte con soporte?"
        )

    mejor = candidatos[0]
    if mejor.score >= settings.match_threshold:
        respuestas_ordenadas = sorted(mejor.pregunta.respuestas, key=lambda r: r.orden)
        partes = [r.contenido for r in respuestas_ordenadas]
        return "\n\n".join(partes)

    return "No estoy seguro de haber entendido bien. ¿Puedes reformular tu pregunta?"


def _generar_respuesta(db: Session, mensaje_usuario: str) -> str:
    """
    Primero prueba contra el inventario real (tabla `properties`, 100%
    Postgres — cero llamadas externas). Si el mensaje calza con zona/tipo
    de alguna propiedad disponible, responde con esas opciones. Si no,
    cae al Q&A general de política/soporte.
    """
    propiedades = buscar_propiedades(db, mensaje_usuario)
    if propiedades:
        return "Encontré estas opciones disponibles:\n\n" + formatear_propiedades(propiedades)
    return _respuesta_qna(db, mensaje_usuario)


async def _enviar_whatsapp(phone: str, texto: str) -> dict:
    """Llama al endpoint sendMessage de Green API para responder al usuario."""
    if not settings.whatsapp_instance_id or not settings.whatsapp_api_token:
        raise HTTPException(
            status_code=500,
            detail=(
                "Faltan las variables WHATSAPP_INSTANCE_ID / WHATSAPP_API_TOKEN "
                "en el entorno de Railway."
            ),
        )

    url = (
        f"{settings.whatsapp_api_url}/waInstance{settings.whatsapp_instance_id}"
        f"/sendMessage/{settings.whatsapp_api_token}"
    )
    payload = {
        "chatId": f"{normalizar_telefono(phone)}@c.us",
        "message": texto,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.ConnectError as exc:
            logger.error("No se pudo conectar a %s: %s", url, exc)
            raise HTTPException(
                status_code=502,
                detail=(
                    f"No se pudo resolver/conectar al host de WhatsApp: '{url}'. "
                    "Revisa que WHATSAPP_API_URL en Railway sea una URL limpia "
                    "(sin corchetes, espacios ni texto de más)."
                ),
            ) from exc

    if resp.status_code >= 400:
        logger.error("Green API respondió %s: %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=502,
            detail=f"Green API respondió {resp.status_code}: {resp.text}",
        )

    return resp.json()


@router.post("/webhook", response_model=WhatsAppWebhookOut)
async def whatsapp_webhook(data: WhatsAppMessageIn, db: Session = Depends(get_db)):
    estado_handover = obtener_o_crear_estado(db, data.phone)

    # 1) El bot ya está en silencio para este número (un humano tomó el
    #    control) -> no se responde nada, sin afectar a otros números.
    if not estado_handover.bot_activo:
        logger.info("Mensaje de %s ignorado: handover activo (modo humano)", data.phone)
        return WhatsAppWebhookOut(
            status="silenciado_por_handover",
            phone=data.phone,
            mensaje_recibido=data.message,
            respuesta_enviada=None,
        )

    contacto, es_nuevo = obtener_o_crear_contacto(db, data.phone)

    # 2) Todavía no sabemos su nombre.
    if not contacto.nombre:
        if es_nuevo:
            # Primera vez que este número escribe: se le da la bienvenida
            # y se le pide el nombre, sin exigir ningún registro previo.
            actualizar_ultima_interaccion(db, contacto)
            await _enviar_whatsapp(data.phone, MENSAJE_PEDIR_NOMBRE)
            return WhatsAppWebhookOut(
                status="pidiendo_nombre",
                phone=data.phone,
                mensaje_recibido=data.message,
                respuesta_enviada=MENSAJE_PEDIR_NOMBRE,
            )

        # Ya se le había pedido el nombre en un mensaje anterior: este
        # mensaje ES la respuesta con su nombre. Se guarda permanentemente.
        contacto = guardar_nombre(db, contacto, data.message)
        actualizar_ultima_interaccion(db, contacto)
        texto = f"¡Mucho gusto, {contacto.nombre}! ¿En qué te puedo ayudar hoy?"
        await _enviar_whatsapp(data.phone, texto)
        return WhatsAppWebhookOut(
            status="nombre_guardado",
            phone=data.phone,
            mensaje_recibido=data.message,
            respuesta_enviada=texto,
        )

    # 3) Ya lo conocemos por su teléfono. ¿Toca volver a saludar por
    #    nombre (nueva sesión) o seguir directo a la respuesta?
    saludar_de_nuevo = debe_saludar_de_nuevo(contacto)
    actualizar_ultima_interaccion(db, contacto)

    # 4) Pide un agente humano -> handover + cortesía, sin pasar por el
    #    matcher automático.
    if solicita_agente_humano(data.message):
        desactivar_bot(db, data.phone, motivo=f"Solicitó agente: '{data.message}'")
        try:
            await _enviar_whatsapp(data.phone, MENSAJE_CORTESIA_HANDOVER)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo enviando mensaje de cortesía de handover")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return WhatsAppWebhookOut(
            status="handover_activado",
            phone=data.phone,
            mensaje_recibido=data.message,
            respuesta_enviada=MENSAJE_CORTESIA_HANDOVER,
        )

    # 5) Flujo normal: responde el bot usando el motor de matching,
    #    reconociendo al usuario por nombre si es una sesión nueva.
    texto_respuesta = _generar_respuesta(db, data.message)
    if saludar_de_nuevo:
        texto_respuesta = f"¡Hola de nuevo, {contacto.nombre}! 👋\n\n{texto_respuesta}"

    try:
        await _enviar_whatsapp(data.phone, texto_respuesta)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fallo inesperado enviando mensaje a WhatsApp")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return WhatsAppWebhookOut(
        status="success",
        phone=data.phone,
        mensaje_recibido=data.message,
        respuesta_enviada=texto_respuesta,
    )
