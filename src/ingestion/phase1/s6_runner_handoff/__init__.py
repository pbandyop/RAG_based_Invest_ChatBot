"""P1-S6 — manifest runner & Phase 2 handoff."""

from ingestion.phase1.s6_runner_handoff.pipeline import (
    PipelineResult,
    run_manifest_pipeline,
    write_pipeline_report,
)

SUBPHASE_ID = "P1-S6"

__all__ = ["SUBPHASE_ID", "PipelineResult", "run_manifest_pipeline", "write_pipeline_report"]
