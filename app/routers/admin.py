from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.handover import activar_bot
from app.loader import DataLoadError, cargar_datos
from app.models import ChatHandover, Contact
from app.schemas import ContactOut, HandoverOut, RecargaOut

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


def _verificar_secreto(x_admin_secret: str = Header(default="")):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="Secreto de administrador inválido")


@router.post(
    "/recargar-datos",
    response_model=RecargaOut,
    dependencies=[Depends(_verificar_secreto)],
)
def recargar_datos(db: Session = Depends(get_db)):
    """
    Vuelve a leer data/categories.yaml y data/qna/*.json y sincroniza la
    base de datos, sin necesidad de reiniciar el servicio. Útil después
    de hacer `git pull` de nuevo contenido en el repo.
    """
    try:
        log = cargar_datos(db)
    except DataLoadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RecargaOut(
        ok=log.errores is None,
        categorias_procesadas=log.categorias_procesadas,
        preguntas_procesadas=log.preguntas_procesadas,
        respuestas_procesadas=log.respuestas_procesadas,
        errores=log.errores,
    )


@router.get(
    "/handover",
    response_model=list[HandoverOut],
    dependencies=[Depends(_verificar_secreto)],
)
def listar_handovers(db: Session = Depends(get_db)):
    """Lista los números que actualmente están en modo humano (bot inactivo)."""
    return db.query(ChatHandover).filter_by(bot_activo=False).all()


@router.post(
    "/handover/{phone}/activar",
    response_model=HandoverOut,
    dependencies=[Depends(_verificar_secreto)],
)
def reactivar_bot_para_numero(phone: str, db: Session = Depends(get_db)):
    """
    Devuelve el bot a modo automático para un número específico —
    úsalo cuando el agente humano termine de atender esa conversación.
    """
    return activar_bot(db, phone)


@router.get(
    "/contactos",
    response_model=list[ContactOut],
    dependencies=[Depends(_verificar_secreto)],
)
def listar_contactos(db: Session = Depends(get_db), limite: int = 100):
    """Lista los contactos conocidos (más recientes primero) — útil para
    confirmar que el nombre quedó guardado correctamente por teléfono."""
    return (
        db.query(Contact)
        .order_by(Contact.ultima_interaccion.desc())
        .limit(limite)
        .all()
    )
