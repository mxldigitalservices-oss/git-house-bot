from pydantic import BaseModel, Field, field_validator

TIPOS_VALIDOS = {"venta", "alquiler"}
ESTADOS_VALIDOS = {"disponible", "reservada", "vendida", "alquilada"}


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


class PropertyIn(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=200)
    tipo: str = Field(..., description="'venta' o 'alquiler'")
    zona: str = Field(..., min_length=1, max_length=120)
    precio: float = Field(..., gt=0)
    habitaciones: int | None = Field(default=None, ge=0)
    banos: int | None = Field(default=None, ge=0)
    area_m2: float | None = Field(default=None, gt=0)
    descripcion: str | None = None
    estado: str = "disponible"

    @field_validator("tipo")
    @classmethod
    def _validar_tipo(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in TIPOS_VALIDOS:
            raise ValueError(f"tipo debe ser uno de {sorted(TIPOS_VALIDOS)}")
        return v

    @field_validator("estado")
    @classmethod
    def _validar_estado(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ESTADOS_VALIDOS:
            raise ValueError(f"estado debe ser uno de {sorted(ESTADOS_VALIDOS)}")
        return v


class PropertyUpdate(BaseModel):
    """Todos los campos opcionales: solo se actualiza lo que se envíe."""

    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    tipo: str | None = None
    zona: str | None = Field(default=None, min_length=1, max_length=120)
    precio: float | None = Field(default=None, gt=0)
    habitaciones: int | None = Field(default=None, ge=0)
    banos: int | None = Field(default=None, ge=0)
    area_m2: float | None = Field(default=None, gt=0)
    descripcion: str | None = None
    estado: str | None = None

    @field_validator("tipo")
    @classmethod
    def _validar_tipo(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in TIPOS_VALIDOS:
            raise ValueError(f"tipo debe ser uno de {sorted(TIPOS_VALIDOS)}")
        return v

    @field_validator("estado")
    @classmethod
    def _validar_estado(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ESTADOS_VALIDOS:
            raise ValueError(f"estado debe ser uno de {sorted(ESTADOS_VALIDOS)}")
        return v


class PropertyOut(BaseModel):
    id: int
    titulo: str
    tipo: str
    zona: str
    precio: float
    habitaciones: int | None = None
    banos: int | None = None
    area_m2: float | None = None
    descripcion: str | None = None
    estado: str

    class Config:
        from_attributes = True
