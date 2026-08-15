import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Healthcheck simple y rápido — es el que usa railway.json
    (healthcheckPath) para decidir si el deploy está sano. Solo valida
    Postgres a propósito: si además chequeara Green API, un hiccup
    temporal del proveedor tumbaría el servicio sin necesidad.
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/health/completo")
async def health_completo(db: Session = Depends(get_db)):
    """
    Verificación de entorno para monitoreo manual/video de validación:
    confirma que FastAPI + PostgreSQL + la pasarela de Green API están
    respondiendo y sincronizados. No es el healthcheck que usa Railway
    para reiniciar el servicio (ver /health).
    """
    resultado: dict = {"fastapi": {"ok": True}}

    try:
        db.execute(text("SELECT 1"))
        resultado["postgres"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        resultado["postgres"] = {"ok": False, "detalle": str(exc)}

    if not settings.whatsapp_instance_id or not settings.whatsapp_api_token:
        resultado["green_api"] = {
            "ok": False,
            "detalle": "Faltan WHATSAPP_INSTANCE_ID / WHATSAPP_API_TOKEN",
        }
    else:
        url = (
            f"{settings.whatsapp_api_url}/waInstance{settings.whatsapp_instance_id}"
            f"/getStateInstance/{settings.whatsapp_api_token}"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            if resp.status_code >= 400:
                resultado["green_api"] = {
                    "ok": False,
                    "detalle": f"Green API respondió {resp.status_code}: {resp.text}",
                }
            else:
                data = resp.json()
                estado = data.get("stateInstance")
                resultado["green_api"] = {
                    "ok": estado == "authorized",
                    "stateInstance": estado,
                }
        except httpx.ConnectError as exc:
            resultado["green_api"] = {
                "ok": False,
                "detalle": f"No se pudo conectar a '{url}': {exc}",
            }
        except Exception as exc:  # noqa: BLE001
            resultado["green_api"] = {"ok": False, "detalle": str(exc)}

    resultado["ok"] = all(v.get("ok") for v in resultado.values() if isinstance(v, dict))
    return resultado
