from app.core.orchestrator import Orchestrator

orchestrator = Orchestrator()

response = orchestrator.ask(
    "Расскажи архитектуру QASkills."
)

print(response)