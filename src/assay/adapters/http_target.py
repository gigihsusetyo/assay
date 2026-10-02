"""HTTP target adapter for calling RAG endpoints."""

from dataclasses import dataclass

import httpx


@dataclass
class TargetResponse:
    """Response from a RAG target."""

    answer: str
    retrieved_contexts: list[dict]
    latency_ms: int
    cost_usd: float | None
    metadata: dict


class TargetError(Exception):
    """Raised when calling the target fails."""

    pass


class HTTPTargetAdapter:
    """Call a RAG endpoint following the Assay adapter contract.

    Request:
        POST {target_url}
        {
            "question": "...",
            "dataset_id": "...",
            "run_id": "..."
        }

    Response:
        {
            "answer": "...",
            "retrieved_contexts": [{"text": "...", "source": "..."}],
            "latency_ms": 1240,
            "cost_usd": 0.0032,
            "metadata": {...}
        }
    """

    def __init__(self, target_url: str, timeout: float = 60.0) -> None:
        self.target_url = target_url
        self.timeout = timeout

    def query(
        self,
        question: str,
        dataset_id: str | None = None,
        run_id: str | None = None,
    ) -> TargetResponse:
        """Send a question to the target and get a response."""
        payload = {
            "question": question,
            "dataset_id": dataset_id,
            "run_id": run_id,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.target_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise TargetError(
                f"Target returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise TargetError(f"Failed to reach target: {e}") from e
        except ValueError as e:
            raise TargetError(f"Invalid JSON response: {e}") from e

        # Validate response
        if "answer" not in data:
            raise TargetError("Response missing 'answer' field")

        return TargetResponse(
            answer=data["answer"],
            retrieved_contexts=data.get("retrieved_contexts", []),
            latency_ms=data.get("latency_ms", 0),
            cost_usd=data.get("cost_usd"),
            metadata=data.get("metadata", {}),
        )
