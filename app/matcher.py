"""
Motor de "inteligencia" del bot: dado un mensaje libre de un usuario,
encuentra la pregunta almacenada más parecida usando similitud difusa
(rapidfuzz) sobre la pregunta original, sus variantes y sus palabras
clave — sin depender de un modelo de lenguaje externo, así el bot
responde rápido y sin costo por llamada.

Si en el futuro se quiere subir de nivel (embeddings + LLM), este
módulo es el único punto que habría que reemplazar: la interfaz
`buscar_mejor_coincidencia` se mantiene igual.
"""
import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Question

settings = get_settings()


def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


@dataclass
class Candidato:
    pregunta: Question
    texto_variante: str
    score: float


def _construir_corpus(pregunta: Question) -> list[str]:
    """Todas las formas de texto asociadas a una pregunta (para comparar)."""
    textos = [pregunta.pregunta]
    textos += [v.texto for v in pregunta.variantes]
    if pregunta.palabras_clave:
        textos.append(" ".join(k.palabra for k in pregunta.palabras_clave))
    return textos


def buscar_mejor_coincidencia(
    db: Session,
    mensaje_usuario: str,
    categoria_slug: str | None = None,
    top_n: int = 5,
) -> list[Candidato]:
    """
    Devuelve hasta `top_n` candidatos ordenados por score descendente
    (0-100). El llamador decide qué hacer con el umbral
    (settings.match_threshold).
    """
    query = db.query(Question).options(
        selectinload(Question.variantes),
        selectinload(Question.palabras_clave),
        selectinload(Question.respuestas),
        selectinload(Question.categoria),
    )
    if categoria_slug:
        query = query.join(Question.categoria).filter_by(slug=categoria_slug)

    preguntas = query.all()
    if not preguntas:
        return []

    mensaje_norm = _normalizar(mensaje_usuario)

    mejores_por_pregunta: list[Candidato] = []
    for pregunta in preguntas:
        corpus = [_normalizar(t) for t in _construir_corpus(pregunta)]
        if not corpus:
            continue
        # token_set_ratio tolera orden distinto de palabras y frases más
        # largas/cortas entre sí (ideal para paráfrasis de usuarios reales)
        mejor_match = process.extractOne(mensaje_norm, corpus, scorer=fuzz.token_set_ratio)
        if mejor_match is None:
            continue
        texto_variante, score, _ = mejor_match
        mejores_por_pregunta.append(
            Candidato(pregunta=pregunta, texto_variante=texto_variante, score=score)
        )

    mejores_por_pregunta.sort(key=lambda c: c.score, reverse=True)
    return mejores_por_pregunta[:top_n]
