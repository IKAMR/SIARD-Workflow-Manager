"""Noark 4 / ePhorte adapter proposal from an existing SIARD QA catalog.

This is not a database query engine, a normative validation, or an automatic
approval. The only included product hints are PUBLIC Noark 4 DTD table names.
The private adapter, with physical column names inferred from the user's
SIARD metadata, is written OUTSIDE the application repository on request.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .model_catalog import MODEL_ROOT, ModelError, load_adapter, load_domain_model

REFERENCE_PATH = MODEL_ROOT / 'standards' / 'noark4_saksarkiv_reference.json'
REPO_ROOT = Path(__file__).resolve().parents[3]


def _norm(value: object) -> str:
    return str(value or '').casefold()


def _json_digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _read_reference() -> dict:
    try:
        ref = json.loads(REFERENCE_PATH.read_text('utf-8'))
    except (OSError, ValueError) as exc:
        raise ModelError(f'Kunne ikke lese Noark 4-referansen: {exc}') from exc
    model = load_domain_model('saksarkiv')
    known = {e['id'] for mod in model['modules'] for e in mod['entities']}
    if ref.get('format_version') != 1 or not isinstance(ref.get('bindings'), list):
        raise ModelError('Ugyldig Noark 4-referansefil')
    for entry in ref['bindings']:
        if entry.get('entity_id') not in known:
            raise ModelError('Noark 4-referansen bruker et ukjent fagbegrep')
        if not str(entry.get('table') or '').strip():
            raise ModelError('Noark 4-referansen mangler tabellnavn')
    if not isinstance(ref.get('relations'), list):
        raise ModelError('Noark 4-referansen mangler relasjoner')
    return ref


def _catalog_from_result(result: dict) -> tuple[list[dict], list[dict]]:
    if not isinstance(result, dict) or not isinstance(result.get('catalog'), list):
        raise ModelError('Forventer QA-JSON med tabellkatalog fra Innholdskontroll')
    catalog = result['catalog']
    if len(catalog) > 100_000:
        raise ModelError('Uventet stor tabellkatalog')
    if not all(isinstance(t, dict) and isinstance(t.get('schema'), str) and
               isinstance(t.get('table'), str) and isinstance(t.get('columns'), list)
               for t in catalog):
        raise ModelError('Katalogen har ugyldige tabell-/kolonnedata')
    declared = (result.get('discovery') or {}).get('declared_relations') or []
    if not isinstance(declared, list):
        raise ModelError('Ugyldig relasjonskatalog')
    return catalog, declared


def _table_index(catalog: list[dict]) -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for table in catalog:
        lookup.setdefault(_norm(table['table']), []).append(table)
    return lookup


def _version_distinct_proposal(table: dict) -> list[dict]:
    """Propose a DISTINCT document/version projection, NEVER count variants as versions.

    Safe only as a proposal, even if these column names occur in SIARD metadata.
    Multiple unrelated columns or a missing version/variant field block inference.
    """
    pk = list(table.get('primary_key') or [])
    versions = [c for c in pk if re.search(r'versjon|version', c, re.I)]
    variants = [c for c in pk if re.search(r'variant', c, re.I)]
    if len(pk) != 3 or len(versions) != 1 or len(variants) != 1 or versions[0] == variants[0]:
        return []
    return [{'id': 'document_versions', 'columns': [c for c in pk if c != variants[0]]}]


def propose_ephorte_adapter(qa_result: dict, *, adapter_id: str = 'ephorte_noark4_proposal') -> tuple[dict, dict]:
    """Build an a4-compatible *unapproved* adapter and an explicit review matrix.

    Only the source's own metadata can supply physical keys and FK columns.
    Ambiguous source names, missing keys and ambiguous FKs are not guessed.
    """
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,99}', adapter_id):
        raise ModelError('Ugyldig adapter-ID')
    ref = _read_reference()
    catalog, foreign_keys = _catalog_from_result(qa_result)
    by_name = _table_index(catalog)
    bindings: list[dict] = []
    review: list[dict] = []
    mapped: dict[str, dict] = {}
    for rule in ref['bindings']:
        terms = [rule['table'], *rule.get('table_aliases', [])]
        found: dict[tuple[str, str], dict] = {}
        for term in terms:
            for t in by_name.get(_norm(term), []):
                found[(_norm(t['schema']), _norm(t['table']))] = t
        note = str(rule.get('note') or '')
        info = {'kind': 'binding', 'id': rule['entity_id'], 'status': '',
                'schema': '', 'table': '', 'columns': '', 'detail': note,
                'sql_reference_id': rule.get('sql_reference_id', ''),
                'sql_reference_previous_id': rule.get('sql_reference_previous_id', ''),
                'metric_id': rule.get('metric_id', '')}
        if len(found) != 1:
            info['status'] = 'MANGLER' if not found else 'FLERTYDIG'
            info['detail'] = (f'Ingen tabell som tilsvarer {terms}' if not found else
                              'Flere kandidater: ' + ', '.join('.'.join(k) for k in sorted(found)))
            review.append(info)
            continue
        t = next(iter(found.values()))
        pk = list(t.get('primary_key') or [])
        columns = {c['name'] for c in t['columns'] if isinstance(c, dict) and
                   isinstance(c.get('name'), str)}
        info.update(schema=t['schema'], table=t['table'], columns=', '.join(pk))
        if not pk or any(x not in columns for x in pk):
            info['status'] = 'NOKKEL_MANGLER'
            info['detail'] = 'Tabell finnes, men deklarert PK er ikke komplett'
        else:
            info['status'] = 'FORSLAG'
        binding = {
            'entity_id': rule['entity_id'], 'review_status': 'proposed',
            'source': {'schema': t['schema'], 'table': t['table']},
            'key': pk if info['status'] == 'FORSLAG' else [],
        }
        if rule['entity_id'] == 'document_representation':
            projection = _version_distinct_proposal(t)
            if projection:
                binding['distinct_metrics'] = projection
                info['detail'] = (note + ' | DISTINCT-maal foreslatt, ikke aktivert').strip()
            else:
                info['detail'] = (note + ' | DISTINCT-versjonsmaal kan ikke utledes sikkert').strip()
        bindings.append(binding)
        mapped[rule['entity_id']] = t
        review.append(info)

    relations: list[dict] = []
    for rule in ref['relations']:
        row = {'kind': 'relation', 'id': rule['id'], 'schema': '',
               'table': '', 'columns': '', 'sql_reference_id': '',
               'sql_reference_previous_id': '', 'metric_id': '', 'status': 'UTEN_KILDE', 'detail': ''}
        child = mapped.get(rule['child'])
        parent = mapped.get(rule['parent'])
        if not child or not parent:
            row['detail'] = 'En eller begge tabellmappinger mangler'
            review.append(row)
            continue
        pkey = list(parent.get('primary_key') or [])
        options = [r for r in foreign_keys
                   if isinstance(r, dict)
                   and _norm(r.get('child_schema')) == _norm(child['schema'])
                   and _norm(r.get('child_table')) == _norm(child['table'])
                   and _norm(r.get('parent_schema')) == _norm(parent['schema'])
                   and _norm(r.get('parent_table')) == _norm(parent['table'])
                   and list(r.get('parent_columns') or []) == pkey
                   and len(r.get('child_columns') or []) == len(pkey)
                   and r.get('status') == 'METADATA_LOEST']
        if len(options) != 1:
            row['status'] = 'MANGLER' if not options else 'FLERTYDIG'
            row['detail'] = ('Ingen entydig deklarert FK til foreldrens PK' if not options else
                             'Flere deklarerte FKer; krever manuell beslutning')
            review.append(row)
            continue
        fk = options[0]
        row['status'] = 'FORSLAG'
        row['schema'] = child['schema']
        row['table'] = child['table']
        row['columns'] = ', '.join(fk['child_columns'])
        row['detail'] = ('Fremmednokkel er deklarert i SIARD. '
                         'Null-krav og relasjonens faglige betydning er ikke godkjent.')
        relations.append({'id': rule['id'], 'review_status': 'proposed',
                          'child': rule['child'], 'parent': rule['parent'],
                          'child_columns': list(fk['child_columns']), 'required': False,
                          'description': 'SIARD-metadata: forslag, vurder for aktivering'})
        review.append(row)

    adapter = {'format_version': 1, 'id': adapter_id,
               'label': 'ePhorte/Noark 4 – FORSLAG fra SIARD-katalog (a5)',
               'domain_id': 'saksarkiv', 'standard_id': 'noark4',
               'visibility': 'restricted',
               'system_hint': 'ePhorte / Noark 4 - må vurderes per uttrekk og systemvariant',
               'description': ('Ubekreftet kartleggingsforslag fra kildens SIARD-metadata. '
                               'INGEN bindinger eller relasjoner kjøres før operatøren '
                               'har kontrollert dem og eksplisitt valgt approved.'),
               'bindings': bindings, 'relations': relations}
    # Reuse the exact validator used when this private file is selected later.
    # Explicitly reject any accidental approved values in a generated proposal.
    if any(x['review_status'] != 'proposed' for x in bindings + relations):
        raise AssertionError('Adapter-generatoren kan ikke godkjenne mappinger')
    summary = {'format_version': 1, 'reference_id': ref['id'],
               'source_name': qa_result.get('source_name', ''),
               'source_catalog_sha256': _json_digest(catalog),
               'reference_sha256': _json_digest(ref),
               'bindings_proposed': len(bindings),
               'bindings_needing_review': len(ref['bindings']),
               'relations_proposed': len(relations),
               'relations_needing_review': len(ref['relations']),
               'mapping_is_approved': False,
               'review': review}
    return adapter, summary


def write_private_proposal(qa_result: dict, output_dir: str | Path,
                           *, adapter_id: str = 'ephorte_noark4_proposal') -> dict:
    """Write user-controlled reference library, never to the public source tree.

    Existing proposals are never overwritten: an operator may have reviewed
    or approved a previous version. No row values from the SIARD are exported.
    """
    output = Path(output_dir).expanduser().resolve()
    if output.is_relative_to(REPO_ROOT):
        raise ModelError('Private adaptere kan ikke lagres i programrepoet')
    if output.exists() and not output.is_dir():
        raise ModelError('Adapterens malmappe er ikke en mappe')
    adapter, summary = propose_ephorte_adapter(qa_result, adapter_id=adapter_id)
    output.mkdir(parents=True, exist_ok=True)
    filename = adapter_id + '.json'
    target = output / filename
    # Fail closed if any of the proposed output paths exists.
    review_json = output / (adapter_id + '_review.json')
    review_csv = output / (adapter_id + '_review.csv')
    for p in (target, review_json, review_csv):
        if p.exists():
            raise ModelError(f'Forslaget finnes allerede og overskrives ikke: {p.name}')
    target.write_text(json.dumps(adapter, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        # Ensure the newly written file is accepted by the a4 runtime loader.
        loaded, _hash = load_adapter(target)
        assert loaded == adapter
        review_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
        with review_csv.open('w', encoding='utf-8-sig', newline='') as out:
            cols = ['kind', 'id', 'status', 'schema', 'table', 'columns',
                    'metric_id', 'sql_reference_id', 'sql_reference_previous_id', 'detail']
            writer = csv.DictWriter(out, fieldnames=cols, delimiter=';')
            writer.writeheader()
            for row in summary['review']:
                safe = {k: str(row.get(k, '')) for k in cols}
                # Avoid spreadsheet formula execution from untrusted table labels.
                safe = {k: ("'" + v if v[:1] in ('=', '+', '-', '@') else v)
                        for k, v in safe.items()}
                writer.writerow(safe)
    except Exception:
        for p in (target, review_json, review_csv):
            p.unlink(missing_ok=True)
        raise
    return {'adapter': str(target), 'review_json': str(review_json),
            'review_csv': str(review_csv), 'summary': {k: v for k,v in summary.items() if k != 'review'}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Skriv uverifisert ePhorte/Noark 4-adapter fra SIARD QA-JSON')
    parser.add_argument('--qa-json', required=True, help='Eksisterende _innholdskontroll.json fra a3/a4')
    parser.add_argument('--output-dir', required=True, help='PRIVATE fagressursbibliotek/adapters/ephorte/noark4')
    parser.add_argument('--adapter-id', default='ephorte_noark4_proposal')
    args = parser.parse_args(argv)
    source = Path(args.qa_json)
    try:
        if source.stat().st_size > 100_000_000:
            raise ModelError('QA-resultatet er for stort')
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        result = write_private_proposal(data, args.output_dir, adapter_id=args.adapter_id)
    except (OSError, ValueError, ModelError) as exc:
        parser.exit(2, f'FEIL: {exc}\n')
    print('Forslag opprettet (ingen mappinger godkjent):')
    print(result['adapter'])
    print(result['review_csv'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
