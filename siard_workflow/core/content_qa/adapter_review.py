"""Metadata-only review of an explicitly selected, unapproved adapter.

No row values are read here. A table/key/column match is NOT a semantic
approval or referential integrity verification.
"""
from __future__ import annotations


def _columns(table: dict | None) -> dict[str, dict]:
    return {c['name']: c for c in (table or {}).get('columns', [])}


def _type_family(value: str) -> str:
    text = str(value or '').upper()
    if text in ('INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT'):
        return 'integer'
    if text.startswith(('FLOAT', 'REAL', 'DOUBLE')):
        return 'floating'
    if text.startswith(('DECIMAL', 'NUMERIC')):
        return 'decimal'
    if any(word in text for word in ('CHAR', 'VARCHAR', 'TEXT', 'CLOB')):
        return 'text'
    return text


def review_adapter_against_catalog(adapter: dict, catalog: list[dict]) -> dict:
    """Verify table/column presence and declared PKs without changing approval."""
    tables = {(t['schema'], t['table']): t for t in catalog}
    by_id = {b['entity_id']: b for b in adapter.get('bindings', [])}
    bindings = []
    for b in adapter.get('bindings', []):
        source = b.get('source') or {}
        table = tables.get((source.get('schema'), source.get('table')))
        cols = _columns(table)
        needed = list(b.get('key') or [])
        needed += [b[key] for key in ('date_column', 'status_column') if b.get(key)]
        needed += [c for m in b.get('distinct_metrics', []) for c in m['columns']]
        missing = list(dict.fromkeys(c for c in needed if c not in cols))
        if table is None:
            status = 'TABELL_MANGLER'
        elif missing:
            status = 'KOLONNER_MANGLER'
        elif list(b.get('key') or []) != list(table.get('primary_key') or []) or not b.get('key'):
            status = 'NOKKEL_KREVER_GJENNOMGANG'
        else:
            status = 'METADATA_TREFF'
        bindings.append({
            'entity_id': b['entity_id'], 'review_status': b['review_status'],
            'schema': source.get('schema', ''), 'table': source.get('table', ''),
            'key_columns': b.get('key') or [],
            'declared_primary_key': (table or {}).get('primary_key') or [],
            'metadata_rows': (table or {}).get('metadata_rows'),
            'actual_rows': (table or {}).get('actual_rows'),
            'missing_columns': missing, 'metadata_status': status,
        })

    relations = []
    for r in adapter.get('relations', []):
        child = by_id.get(r['child']) or {}
        parent = by_id.get(r['parent']) or {}
        csrc = child.get('source') or {}
        psrc = parent.get('source') or {}
        ct = tables.get((csrc.get('schema'), csrc.get('table')))
        pt = tables.get((psrc.get('schema'), psrc.get('table')))
        ccols, pcols = _columns(ct), _columns(pt)
        child_keys, parent_keys = list(r.get('child_columns') or []), list(parent.get('key') or [])
        missing = [c for c in child_keys if c not in ccols] + [c for c in parent_keys if c not in pcols]
        type_warnings = []
        if ct is None or pt is None:
            status = 'TABELL_MANGLER'
        elif missing:
            status = 'KOLONNER_MANGLER'
        elif not parent_keys or len(child_keys) != len(parent_keys):
            status = 'NOKKEL_PARING_MANGLER'
        else:
            for cc, pc in zip(child_keys, parent_keys):
                ctype, ptype = ccols[cc].get('sql_type', ''), pcols[pc].get('sql_type', '')
                if _type_family(ctype) != _type_family(ptype):
                    type_warnings.append(f'{cc} ({ctype}) / {pc} ({ptype})')
            status = 'TYPE_GJENNOMGANG' if type_warnings else 'KOLONNER_FUNNET'
        relations.append({
            'id': r['id'], 'review_status': r['review_status'],
            'child': r['child'], 'parent': r['parent'],
            'child_table': csrc.get('table', ''), 'parent_table': psrc.get('table', ''),
            'child_columns': child_keys, 'parent_key_columns': parent_keys,
            'type_warnings': type_warnings, 'metadata_status': status,
            'declared_fk_verified': False,
        })

    return {
        'format_version': 1, 'method': 'ADAPTER_MOT_SIARD_METADATA_KUN',
        'review_required': True, 'adapter_id': adapter.get('id'),
        'domain_id': adapter.get('domain_id'),
        'approval_policy': 'INGEN_AUTOMATISK_GODKJENNING',
        'notes': [
            'Tabell-, felt- og PK-treff beviser ikke faglig ekvivalens.',
            'Relasjonene er forslag, ingen datareferanser er kontrollert.',
            'INT/FLOAT-forskjeller krever vurdering av verdi- og typekonvertering.',
            'CLOB/NCLOB kan vaere faglige tekstverdier, ikke automatisk dokumentfiler.',
        ],
        'summary': {
            'bindings': len(bindings),
            'bindings_metadata_match': sum(x['metadata_status'] == 'METADATA_TREFF' for x in bindings),
            'bindings_metadata_issues': sum(x['metadata_status'] != 'METADATA_TREFF' for x in bindings),
            'bindings_proposed': sum(x['review_status'] == 'proposed' for x in bindings),
            'bindings_approved': sum(x['review_status'] == 'approved' for x in bindings),
            'relations': len(relations),
            'relations_columns_found': sum(x['metadata_status'] in ('KOLONNER_FUNNET', 'TYPE_GJENNOMGANG') for x in relations),
            'relations_type_review': sum(x['metadata_status'] == 'TYPE_GJENNOMGANG' for x in relations),
            'relations_approved': sum(x['review_status'] == 'approved' for x in relations),
        },
        'bindings': bindings, 'relations': relations,
    }
