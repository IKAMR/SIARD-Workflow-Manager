"""Dispatch approved, optional domain metrics without vendor code in generic QA.

No adapter, no standard id, or an unknown standard => no semantic metrics.
No physical table mapping is ever inferred from a schema name or domain alone.
"""
from __future__ import annotations


def build_domain_metrics(result: dict, model_context: dict) -> dict | None:
    standard = (model_context or {}).get('standard_id')
    if standard == 'noark4':
        from .semantic_results import build_noark4_metrics
        return build_noark4_metrics(result, model_context)
    return None
