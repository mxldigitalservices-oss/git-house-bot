from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Category, Question
from app.schemas import CategoryOut, QuestionOut

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.get("", response_model=list[CategoryOut])
def listar_categorias(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.nombre).all()


@router.get("/{slug}/preguntas", response_model=list[QuestionOut])
def listar_preguntas_por_categoria(slug: str, db: Session = Depends(get_db)):
    categoria = db.query(Category).filter_by(slug=slug).one_or_none()
    if categoria is None:
        raise HTTPException(status_code=404, detail=f"Categoría '{slug}' no encontrada")

    preguntas = (
        db.query(Question)
        .options(selectinload(Question.respuestas))
        .filter_by(category_id=categoria.id)
        .all()
    )
    return [
        QuestionOut(id=p.external_id, pregunta=p.pregunta, respuestas=p.respuestas)
        for p in preguntas
    ]
