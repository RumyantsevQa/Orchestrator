from pydantic import BaseModel


class UserRequest(BaseModel):
    text: str


class OrchestratorResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None