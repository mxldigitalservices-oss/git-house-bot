from pydantic import BaseModel, Field


class AnswerOut(BaseModel):
    tipo: str
    contenido: str
    meta: dict | None = None

    class Config:
        from_attributes = True


class QuestionOut(BaseModel):
    id: str
    pregunta: str
    respuestas: list[AnswerOut]

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    slug: str
    nombre: str
    descripcion: str | None = None

    class Config:
        from_attributes = True


class ConsultaIn(BaseModel):
    mensaje: str = Field(..., min_length=1, max_length=2000)
    categoria: str | None = Field(
        default=None, description="Restringe la búsqueda a una categoría por slug"
    )


class SugerenciaOut(BaseModel):
    pregunta_id: str
    pregunta: str
    score: float


class ConsultaOut(BaseModel):
    encontrado: bool
    score: float | None = None
    pregunta_id: str | None = None
    pregunta: str | None = None
    respuestas: list[AnswerOut] = []
    sugerencias: list[SugerenciaOut] = []
    mensaje_fallback: str | None = None


class RecargaOut(BaseModel):
    ok: bool
    categorias_procesadas: int
    preguntas_procesadas: int
    respuestas_procesadas: int
    errores: str | None = None


class HandoverOut(BaseModel):
    phone: str
    bot_activo: bool
    motivo: str | None = None

    class Config:
        from_attributes = True


class ContactOut(BaseModel):
    phone: str
    nombre: str | None = None

    class Config:
        from_attributes = True
