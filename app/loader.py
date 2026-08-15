"""
Carga dinámica de la data estructurada (data/categories.yaml + data/qna/*.json)
hacia las tablas relacionales.

Diseño idempotente: se puede correr en cada arranque (o vía
POST /admin/recargar-datos) sin duplicar filas. Usa slug (categorías) y
external_id (preguntas) como claves naturales para hacer upsert.
"""
import json
import logging
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Answer, Category, LoadLog, Question, QuestionKeyword, QuestionVariant

logger = logging.getLogger("githouse.loader")
settings = get_settings()


class DataLoadError(Exception):
    pass


def _leer_categorias(data_dir: Path) -> list[dict]:
    ruta = data_dir / "categories.yaml"
    if not ruta.exists():
        raise DataLoadError(f"No se encontró {ruta}")
    with open(ruta, encoding="utf-8") as f:
        contenido = yaml.safe_load(f) or {}
    return contenido.get("categorias", [])


def _leer_archivos_qna(data_dir: Path) -> list[dict]:
    carpeta = data_dir / "qna"
    if not carpeta.exists():
        return []
    archivos = sorted(carpeta.glob("*.json"))
    bloques = []
    for archivo in archivos:
        try:
            with open(archivo, encoding="utf-8") as f:
                bloques.append(json.load(f))
        except json.JSONDecodeError as exc:
            raise DataLoadError(f"JSON inválido en {archivo.name}: {exc}") from exc
    return bloques


def _upsert_categoria(db: Session, cat_data: dict) -> Category:
    slug = cat_data["slug"]
    categoria = db.query(Category).filter_by(slug=slug).one_or_none()
    if categoria is None:
        categoria = Category(slug=slug)
        db.add(categoria)
    categoria.nombre = cat_data.get("nombre", slug)
    categoria.descripcion = cat_data.get("descripcion")
    return categoria


def _upsert_pregunta(db: Session, categoria: Category, q_data: dict) -> Question:
    external_id = q_data["id"]
    pregunta = db.query(Question).filter_by(external_id=external_id).one_or_none()
    if pregunta is None:
        pregunta = Question(external_id=external_id)
        db.add(pregunta)

    pregunta.categoria = categoria
    pregunta.pregunta = q_data["pregunta"]

    # Reemplaza variantes/keywords/respuestas por completo en cada carga
    # para que el repo (fuente de verdad) siempre gane sobre lo que había
    # quedado en la base de una carga anterior.
    pregunta.variantes.clear()
    for texto in q_data.get("variantes", []):
        pregunta.variantes.append(QuestionVariant(texto=texto))

    pregunta.palabras_clave.clear()
    for palabra in q_data.get("palabras_clave", []):
        pregunta.palabras_clave.append(QuestionKeyword(palabra=palabra))

    pregunta.respuestas.clear()
    for idx, resp in enumerate(q_data.get("respuestas", [])):
        pregunta.respuestas.append(
            Answer(
                tipo=resp.get("tipo", "texto"),
                contenido=resp["contenido"],
                meta=resp.get("meta"),
                orden=idx,
            )
        )
    return pregunta


def cargar_datos(db: Session) -> LoadLog:
    """Punto de entrada único: lee todo data/ y sincroniza la base de datos."""
    data_dir = Path(settings.data_dir)
    log = LoadLog()

    try:
        categorias_raw = _leer_categorias(data_dir)
        categorias_por_slug: dict[str, Category] = {}

        for cat_data in categorias_raw:
            categoria = _upsert_categoria(db, cat_data)
            db.flush()  # asegura categoria.id antes de asociarle preguntas
            categorias_por_slug[categoria.slug] = categoria
            log.categorias_procesadas += 1

        bloques_qna = _leer_archivos_qna(data_dir)
        for bloque in bloques_qna:
            slug_categoria = bloque.get("categoria")
            categoria = categorias_por_slug.get(slug_categoria)
            if categoria is None:
                raise DataLoadError(
                    f"El archivo de preguntas referencia la categoría "
                    f"'{slug_categoria}', que no existe en categories.yaml"
                )
            for q_data in bloque.get("preguntas", []):
                pregunta = _upsert_pregunta(db, categoria, q_data)
                log.preguntas_procesadas += 1
                log.respuestas_procesadas += len(q_data.get("respuestas", []))

        db.commit()
        logger.info(
            "Carga de datos OK: %s categorías, %s preguntas, %s respuestas",
            log.categorias_procesadas,
            log.preguntas_procesadas,
            log.respuestas_procesadas,
        )
    except Exception as exc:  # noqa: BLE001 — se registra y se relanza controlado
        db.rollback()
        log.errores = str(exc)
        logger.exception("Fallo al cargar datos estructurados")
        db.add(log)
        db.commit()
        raise

    db.add(log)
    db.commit()
    return log
