# Assay

**The release gate for RAG systems.**

Assay runs a golden dataset against a RAG endpoint, compares the results to a pinned baseline, and fails the deployment if quality, latency, or cost regress beyond defined thresholds.

## Status

Early development. Not ready for use yet.

## What Assay Does

- Runs evaluation datasets against any RAG endpoint
- Compares results to a baseline
- Fails CI when quality regresses
- Produces reports that non-engineers can read

## What Assay Is Not

- Not a RAG framework
- Not a metrics library
- Not an observability platform
- Not a general LLM evaluation tool

## Roadmap

- **MVP (3-4 weeks):** Core evaluation, CLI, Docker, CI gate, cloud demo
- **Phase 2 (2 weeks):** Go execution plane
- **Phase 3 (2 weeks):** Real cloud Kubernetes
- **Phase 4 (2 weeks):** Observability and integration

## License

Apache 2.0. See [LICENSE](LICENSE).

## Links

- Domain: [assay.web.id](https://assay.web.id)
- GitHub: [github.com/gigihsusetyo/assay](https://github.com/gigihsusetyo/assay)
