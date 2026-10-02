# ADR-002: HTTP Adapter Contract

**Status:** Accepted
**Date:** 2 October 2026

## Context

Assay evaluates RAG systems. The question is: how does Assay talk to a RAG system?

There are a few options. Assay could import the RAG system as a Python library. Assay could require the RAG system to use a specific framework. Assay could call the RAG system over HTTP.

I chose HTTP. The reason is simple: I do not want Assay to become a RAG framework.

If Assay imports the RAG system as a library, then Assay is tied to Python. If Assay requires a specific framework, then Assay is tied to that framework. Both options make Assay less useful for teams that already have a working RAG system in production.

HTTP is universal. Any RAG system can expose an HTTP endpoint. Any language can implement it. Any deployment can reach it.

## Decision

Assay calls a standard HTTP endpoint. The contract is:

Request:

```json
{
  "question": "How do I configure SSO with Okta?",
  "dataset_id": "support-golden-v3",
  "run_id": "run_2026_09_29_001"
}
```

Response:

```json
{
  "answer": "To configure SSO with Okta...",
  "retrieved_contexts": [
    {"text": "...", "source": "docs/sso.md", "score": 0.87}
  ],
  "latency_ms": 1240,
  "cost_usd": 0.0032,
  "metadata": {"model": "gpt-4", "embedding": "text-embedding-3-small"}
}
```

Any RAG system that implements this contract can be evaluated. Assay does not care what is inside.

## Consequences

What I gain:

- Assay is language-agnostic. Python, Go, Node, anything.
- Assay is framework-agnostic. LangChain, LlamaIndex, custom, anything.
- Assay does not need to know how retrieval works. It only needs the result.
- Testing is easier. A mock RAG endpoint is enough.

What I sacrifice:

- Assay cannot inspect internal state of the RAG system. It only sees what the endpoint returns.
- Assay cannot compute retrieval metrics that need internal data, unless the endpoint exposes them.
- The contract must be documented clearly. If it changes, it breaks integration.

Plan:

- Version the contract. If it changes, add a version field.
- Document the contract in the README.
- Provide a reference implementation in the mock RAG example.

---

# ADR-002: Kontrak HTTP Adapter

**Status:** Diterima
**Tanggal:** 2 Oktober 2026

## Konteks

Assay mengevaluasi sistem RAG. Pertanyaannya: bagaimana Assay berkomunikasi dengan sistem RAG?

Ada beberapa opsi. Assay bisa import sistem RAG sebagai library Python. Assay bisa minta sistem RAG pakai framework tertentu. Assay bisa panggil sistem RAG lewat HTTP.

Saya pilih HTTP. Alasannya sederhana: saya tidak mau Assay jadi RAG framework.

Kalau Assay import sistem RAG sebagai library, maka Assay terikat ke Python. Kalau Assay minta framework tertentu, maka Assay terikat ke framework itu. Kedua opsi membuat Assay kurang berguna untuk tim yang sudah punya sistem RAG jalan di production.

HTTP itu universal. Sistem RAG apa pun bisa expose HTTP endpoint. Bahasa apa pun bisa implement. Deployment apa pun bisa reach.

## Keputusan

Assay panggil HTTP endpoint standar. Kontraknya:

Request:

```json
{
  "question": "How do I configure SSO with Okta?",
  "dataset_id": "support-golden-v3",
  "run_id": "run_2026_09_29_001"
}
```

Response:

```json
{
  "answer": "To configure SSO with Okta...",
  "retrieved_contexts": [
    {"text": "...", "source": "docs/sso.md", "score": 0.87}
  ],
  "latency_ms": 1240,
  "cost_usd": 0.0032,
  "metadata": {"model": "gpt-4", "embedding": "text-embedding-3-small"}
}
```

Sistem RAG apa pun yang implement kontrak ini bisa dievaluasi. Assay tidak peduli isinya.

## Konsekuensi

Yang saya dapat:

- Assay language-agnostic. Python, Go, Node, apa saja.
- Assay framework-agnostic. LangChain, LlamaIndex, custom, apa saja.
- Assay tidak perlu tahu cara retrieval bekerja. Cuma butuh hasilnya.
- Testing lebih mudah. Mock RAG endpoint cukup.

Yang saya korbankan:

- Assay tidak bisa inspect internal state sistem RAG. Cuma lihat apa yang endpoint return.
- Assay tidak bisa hitung retrieval metrics yang butuh data internal, kecuali endpoint expose.
- Kontrak harus didokumentasikan jelas. Kalau berubah, integration rusak.

Rencana:

- Version kontrak. Kalau berubah, tambah field version.
- Dokumentasikan kontrak di README.
- Sediakan reference implementation di contoh mock RAG.