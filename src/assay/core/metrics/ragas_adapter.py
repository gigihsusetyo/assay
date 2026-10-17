"""Adapter for Ragas metrics (optional).

This module is a thin wrapper around the Ragas library. It is
optional: if Ragas is not installed, importing this module does not
fail. Calling evaluate_ragas raises a clear error telling the user
how to install it.

The adapter uses the same LLM provider that Assay's judge uses
(BYOK). It does not require a separate API key.
"""

from dataclasses import dataclass

from assay.config import settings


@dataclass
class RagasResult:
    """Result of a Ragas evaluation."""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    error: str | None = None


def _is_ragas_installed() -> bool:
    """Check whether the ragas package is importable."""
    try:
        import ragas  # noqa: F401

        return True
    except ImportError:
        return False


def evaluate_ragas(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None = None,
) -> RagasResult:
    """Evaluate a single (question, answer, contexts) triplet using Ragas.

    Requires the optional `ragas` dependency. Install it with:

        pip install "assay[ragas]"

    Uses the first configured Assay judge provider as the LLM for Ragas.

    Returns a RagasResult. If Ragas is not installed, returns a
    RagasResult with an error message.
    """
    if not _is_ragas_installed():
        return RagasResult(
            error=(
                "Ragas is not installed. Install it with: "
                "pip install \"assay[ragas]\""
            )
        )

    if not settings.judge_enabled:
        return RagasResult(
            error=(
                "Ragas requires an LLM provider. Configure a judge "
                "provider in .env first."
            )
        )

    try:
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.dataset_schema import EvaluationDataset
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as e:
        return RagasResult(
            error=f"Ragas dependency missing: {e}. Try pip install \"assay[ragas]\"."
        )

    provider = settings.judge_providers[0]

    try:
        llm = ChatOpenAI(
            model=provider.model,
            api_key=provider.api_key,
            base_url=provider.base_url,
            timeout=provider.timeout,
            temperature=0.0,
        )
    except Exception as e:
        return RagasResult(error=f"Failed to initialize Ragas LLM: {e}")

    try:
        from ragas import SingleTurnSample

        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
            reference=ground_truth or "",
        )

        dataset = EvaluationDataset(samples=[sample])

        result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
            llm=LangchainLLMWrapper(llm),
        )

        # Result is a dict-like object
        df = result.to_pandas()
        row = df.iloc[0]

        return RagasResult(
            faithfulness=float(row.get("faithfulness", float("nan"))),
            answer_relevancy=float(row.get("answer_relevancy", float("nan"))),
            context_precision=float(row.get("context_precision", float("nan"))),
            context_recall=float(row.get("context_recall", float("nan"))),
        )
    except Exception as e:
        return RagasResult(error=f"Ragas evaluation failed: {e}")
