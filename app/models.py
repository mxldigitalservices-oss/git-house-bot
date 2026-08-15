"""
Modelos relacionales del "cerebro" del bot.

Diseño:
  Category (1) --- (N) Question (1) --- (N) Answer
  Question (1) --- (N) QuestionVariant   (variantes/paráfrasis para matching)
  Question (1) --- (N) QuestionKeyword   (palabras clave para matching)

Todo se crea dinámicamente vía Base.metadata.create_all() al arrancar
(app/lifespan en main.py) — no hay SQL estático que mantener a mano.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    preguntas: Mapped[list["Question"]] = relationship(
        back_populates="categoria", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("external_id", name="uq_question_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # external_id = el "id" declarado en el JSON/YAML de origen (ej. "ventas_001").
    # Sirve para hacer upsert idempotente en cada carga, sin duplicar filas.
    external_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    pregunta: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    categoria: Mapped["Category"] = relationship(back_populates="preguntas")
    respuestas: Mapped[list["Answer"]] = relationship(
        back_populates="pregunta_ref", cascade="all, delete-orphan"
    )
    variantes: Mapped[list["QuestionVariant"]] = relationship(
        back_populates="pregunta_ref", cascade="all, delete-orphan"
    )
    palabras_clave: Mapped[list["QuestionKeyword"]] = relationship(
        back_populates="pregunta_ref", cascade="all, delete-orphan"
    )


class QuestionVariant(Base):
    """Paráfrasis reales de usuarios ('quiero vender mi casa', etc.)."""

    __tablename__ = "question_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    pregunta_ref: Mapped["Question"] = relationship(back_populates="variantes")


class QuestionKeyword(Base):
    __tablename__ = "question_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    palabra: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    pregunta_ref: Mapped["Question"] = relationship(back_populates="palabras_clave")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), default="texto")  # texto | link | imagen | accion
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    # metadata libre (ej: {"url": "...", "boton": "Ver más"}) para que el
    # frontend/n8n decida cómo renderizar la respuesta sin tocar el modelo.
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    pregunta_ref: Mapped["Question"] = relationship(back_populates="respuestas")


class LoadLog(Base):
    """Auditoría de cada carga/recarga de datos (para debug en producción)."""

    __tablename__ = "load_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ejecutado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    categorias_procesadas: Mapped[int] = mapped_column(Integer, default=0)
    preguntas_procesadas: Mapped[int] = mapped_column(Integer, default=0)
    respuestas_procesadas: Mapped[int] = mapped_column(Integer, default=0)
    errores: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChatHandover(Base):
    """
    Estado de "modo humano" por número de teléfono.

    bot_activo=True  -> el bot responde normalmente a ese número.
    bot_activo=False -> el bot se queda en silencio absoluto para ese
                         número (un humano tomó el control); los demás
                         números siguen recibiendo respuestas automáticas
                         sin ningún efecto entre sí, porque el estado
                         vive por phone, no de forma global.
    """

    __tablename__ = "chat_handovers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    bot_activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Contact(Base):
    """
    Memoria permanente de cada número que ha escrito.

    nombre=None  -> todavía no sabemos su nombre (se le pidió y estamos
                     esperando su respuesta, o es la primerísima vez).
    ultima_interaccion se usa para decidir si toca volver a saludar por
    nombre (nueva "sesión" de conversación) o simplemente responder.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ultima_interaccion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
