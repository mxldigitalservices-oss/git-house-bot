from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.matcher import buscar_mejor_coincidencia
from app.schemas import AnswerOut, ConsultaIn, ConsultaOut, SugerenciaOut

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


@router.post("/consultar", response_model=ConsultaOut)
def consultar(payload: ConsultaIn, db: Session = Depends(get_db)):
    candidatos = buscar_mejor_coincidencia(
        db, payload.mensaje, categoria_slug=payload.categoria
    )

    if not candidatos:
        return ConsultaOut(
            encontrado=False,
            mensaje_fallback="Todavía no tengo información sobre eso. ¿Quieres que te conecte con soporte?",
        )

    mejor = candidatos[0]

    if mejor.score >= settings.match_threshold:
        respuestas_ordenadas = sorted(mejor.pregunta.respuestas, key=lambda r: r.orden)
        return ConsultaOut(
            encontrado=True,
            score=round(mejor.score, 2),
            pregunta_id=mejor.pregunta.external_id,
            pregunta=mejor.pregunta.pregunta,
            respuestas=[AnswerOut.model_validate(r) for r in respuestas_ordenadas],
        )

    # No hay una coincidencia lo bastante fuerte: se ofrecen sugerencias
    # en vez de inventar una respuesta.
    sugerencias = [
        SugerenciaOut(
            pregunta_id=c.pregunta.external_id,
            pregunta=c.pregunta.pregunta,
            score=round(c.score, 2),
        )
        for c in candidatos[: settings.max_sugerencias]
    ]
    return ConsultaOut(
        encontrado=False,
        mensaje_fallback="No estoy seguro de haber entendido bien. ¿Te refieres a alguna de estas preguntas?",
        sugerencias=sugerencias,
    )
