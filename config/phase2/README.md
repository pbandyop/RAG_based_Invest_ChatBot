# Phase 2 — chunking, embeddings, index

**Inputs:** `data/phase1/normalized/{run_id}/*.normalized.json` (P1-S4).

**Outputs:** `data/phase2/index/{run_id}/` — `manifest.json`, `chunk_metadata.json`, `chunks.jsonl`, `index.faiss`.

**Embedding model (pilot):** `BAAI/bge-small-en-v1.5` (see `defaults.json`; override with CLI `--model`).

## Setup

```bash
pip install -r requirements.txt
```

## Build index

```bash
python scripts/run_phase2_build_index.py --overwrite
```

Optional smoke retrieval (prints top hits for [golden_queries.json](golden_queries.json)):

```bash
python scripts/run_phase2_build_index.py --overwrite --smoke
```

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §5 and [docs/edge-cases/phase-2-edge-cases.md](../../docs/edge-cases/phase-2-edge-cases.md).
