from fastapi import FastAPI

from app.core.database import engine
from app.models.models import Base
from app.api import agent, hitl, restore

app = FastAPI(
    title="Progressive Autonomy Agent Harness",
    description=(
        "Structural guardrails for an LLM-driven content queue: reversible-"
        "by-default mutations and trust-calibrated progressive autonomy."
    ),
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    # In a larger production system this would be Alembic migrations run
    # from the container entrypoint. For this exercise, declarative
    # create_all is sufficient and idempotent (no-ops on existing tables).
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "service": "agent-harness",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


app.include_router(agent.router)
app.include_router(hitl.router)
app.include_router(restore.router)
