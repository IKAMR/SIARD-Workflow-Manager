"""Stable, explicit QA aggregates for later DWM import.

A semantic metric is created only for a SELECTED and approved Noark 4 adapter.
'Not measured' is never serialized as zero. These are observational results,
not a statement that the full Noark 4 specification has been validated.
"""
from __future__ import annotations

import json
from .ephorte_noark4 import REFERENCE_PATH


def build_noark4_metrics(result: dict, model_context: dict) -> dict | None:
    if (model_context.get('domain_id') != 'saksarkiv' or
            model_context.get('standard_id') != 'noark4'):
        return None
    reference = json.loads(REFERENCE_PATH.read_text('utf-8'))
    carriers = {x['id']: x for x in result.get('carriers', [])}
    table_states = {f"{t['schema']}.{t['table']}": t for t in result.get('catalog', [])}
    metrics = []
    for entry in reference['bindings']:
        carrier = carriers.get(entry['entity_id'], {})
        value = carrier.get('rows')
        state = ('not_measured' if value is None else
                 'measured_with_findings' if carrier.get('status') == 'AVVIK' else
                 'measured' if carrier.get('status') == 'OK' else 'not_measured')
        source_table = carrier.get('table') or None
        tab = table_states.get(source_table) or {}
        if state == 'measured' and (tab.get('status') not in (None, 'OK') or
                                    tab.get('pk_status') == 'AVVIK'):
            state = 'measured_with_findings'
        if state == 'not_measured':
            value = None
        metrics.append({
            'metric_id': entry['metric_id'], 'concept_id': entry['entity_id'],
            'value': value, 'unit': 'source_rows', 'state': state,
            'scope': 'whole_extraction', 'method': 'approved_carrier_row_count',
            'source_table': source_table,
            'legacy_sql_reference_id': entry.get('sql_reference_id'),
            'legacy_sql_previous_id': entry.get('sql_reference_previous_id'),
            'legacy_sql_execution': False,
        })
        if entry['entity_id'] == 'document_representation':
            distinct = carrier.get('distinct_counts') or {}
            variants = distinct.get('document_versions')
            misses = (carrier.get('distinct_missing') or {}).get('document_versions')
            distinct_state = (state if state != 'not_measured' and variants is not None else
                              'not_measured')
            metrics.append({
                'metric_id': 'document_version.count',
                'concept_id': 'document_version',
                'value': variants if distinct_state != 'not_measured' else None,
                'unit': 'distinct_document_version_keys',
                'state': distinct_state,
                'scope': 'whole_extraction',
                'method': 'approved_distinct_projection_excluding_variant',
                'excluded_null_rows': misses if distinct_state != 'not_measured' else None,
                'source_table': carrier.get('table') or None,
                'legacy_sql_reference_id': None,
                'legacy_sql_execution': False,
            })
    return {
        'format_version': 1, 'model_id': 'saksarkiv',
        'standard_id': 'noark4', 'reference_id': reference['id'],
        'status': 'partial_observational_evidence',
        'all_requirements_validated': False,
        'source_name': result.get('source_name'),
        'source_type': result.get('source_type'),
        'source_selection': result.get('source_selection'),
        'profile_sha256': result.get('profile_sha256'),
        'model_sha256': model_context.get('model_sha256'),
        'adapter_id': model_context.get('adapter_id'),
        'adapter_sha256': model_context.get('adapter_sha256'),
        'approved_bindings': model_context.get('bindings_applied'),
        'notes': ('Ingen opprinnelige MySQL-sporringer kjoert. '
                  'SQL-referanse-IDer er historiske kryssreferanser, '
                  'ikke prov pa full semantisk ekvivalens.'),
        'metrics': metrics,
    }
