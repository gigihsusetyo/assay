"""Mock RAG endpoint for testing Assay.

Run with:
    uvicorn examples.mock_rag.app:app --port 9000
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock RAG", version="0.1.0")


class QueryRequest(BaseModel):
    question: str
    dataset_id: str | None = None
    run_id: str | None = None


class Context(BaseModel):
    text: str
    source: str = "mock"


class QueryResponse(BaseModel):
    answer: str
    retrieved_contexts: list[Context]
    latency_ms: int
    cost_usd: float
    metadata: dict


# Canned responses keyed by question substring
CANNED = {
    "password": {
        "answer": "Go to settings and click reset password. Follow the email link to complete the reset.",
        "contexts": [
            {"text": "You can reset your password by going to settings and clicking reset password.", "source": "faq/password.md"},
            {"text": "Follow the email link to complete the password reset process.", "source": "faq/password.md"},
        ],
    },
    "sso": {
        "answer": "To configure SSO, go to settings, select SSO, and enter your provider details.",
        "contexts": [
            {"text": "SSO configuration is available in the settings page under the SSO section.", "source": "docs/sso.md"},
        ],
    },
    "default": {
        "answer": "I do not have enough information to answer that question.",
        "contexts": [
            {"text": "General help documentation.", "source": "docs/general.md"},
        ],
    },
}


@app.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest) -> QueryResponse:
    """Return a canned response based on the question."""
    q_lower = payload.question.lower()
    for key, value in CANNED.items():
        if key != "default" and key in q_lower:
            return QueryResponse(
                answer=value["answer"],
                retrieved_contexts=[Context(**c) for c in value["contexts"]],
                latency_ms=1200,
                cost_usd=0.002,
                metadata={"model": "mock", "provider": "canned"},
            )
    default = CANNED["default"]
    return QueryResponse(
        answer=default["answer"],
        retrieved_contexts=[Context(**c) for c in default["contexts"]],
        latency_ms=800,
        cost_usd=0.001,
        metadata={"model": "mock", "provider": "canned"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}
