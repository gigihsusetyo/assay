"""Assay API entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Assay",
    description="The release gate for RAG systems",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
