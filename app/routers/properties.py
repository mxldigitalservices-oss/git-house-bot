"""
CRUD del inventario de propiedades — vive enteramente en la tabla
`properties` de Postgres. Lectura pública (para que el bot y cualquier
otro canal la consulten sin fricción), escritura protegida con el mismo
X-Admin-Secret que ya usan /admin/recargar-datos y el handover.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Property
from app.schemas import PropertyIn, PropertyOut, PropertyUpdate

router = APIRouter(prefix="/propiedades", tags=["propiedades"])
settings = get_settings()


def _verificar_secreto(x_admin_secret: str = Header(default="")):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="Secreto de administrador inválido")


@router.get("", response_model=list[PropertyOut])
def listar_propiedades(
    db: Session = Depends(get_db),
    zona: str | None = None,
    tipo: str | None = None,
    estado: str = "disponible",
    limite: int = 50,
):
    """Filtra por zona (coincidencia parcial), tipo y estado — una sola
    consulta indexada, sin necesidad de traer todo el inventario."""
    query = db.query(Property)
    if estado:
        query = query.filter(Property.estado == estado)
    if zona:
        query = query.filter(Property.zona.ilike(f"%{zona}%"))
    if tipo:
        query = query.filter(Property.tipo == tipo.lower())
    return query.order_by(Property.actualizado_en.desc()).limit(limite).all()


@router.get("/{propiedad_id}", response_model=PropertyOut)
def obtener_propiedad(propiedad_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, propiedad_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    return prop


@router.post("", response_model=PropertyOut, dependencies=[Depends(_verificar_secreto)])
def crear_propiedad(data: PropertyIn, db: Session = Depends(get_db)):
    """Agregar la propiedad #6, #15 o #20: una fila nueva, sin redeploy."""
    prop = Property(**data.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.put(
    "/{propiedad_id}", response_model=PropertyOut, dependencies=[Depends(_verificar_secreto)]
)
def actualizar_propiedad(propiedad_id: int, data: PropertyUpdate, db: Session = Depends(get_db)):
    prop = db.get(Property, propiedad_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(prop, campo, valor)

    db.commit()
    db.refresh(prop)
    return prop


@router.delete("/{propiedad_id}", dependencies=[Depends(_verificar_secreto)])
def borrar_propiedad(propiedad_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, propiedad_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    db.delete(prop)
    db.commit()
    return {"ok": True, "eliminado_id": propiedad_id}
