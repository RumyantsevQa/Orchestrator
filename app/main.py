from fastapi import FastAPI
from app.core.orchestrator import Orchestrator
from app.core.models import UserRequest

app = FastAPI(title="Orchestrator")

orchestrator = Orchestrator()


@app.get("/")
def root():
    return {"message": "Orchestrator is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/process")
def process(request: str):
    result = orchestrator.process(
    UserRequest(text=request))
    return result