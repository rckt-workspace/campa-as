from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
