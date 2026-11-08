"""Versioned, data-only system-type models for content QA.

The catalog contains generic domain semantics, never proprietary table maps.
Source-specific bindings live in separately selected adapter files.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .profile import ProfileError, validate_profile


class ModelError(ValueError):
    """Invalid model or adapter configuration (no source data was modified)."""


MODEL_ROOT = Path(__file__).resolve().parents[2] / 'models'
_ID = re.compile(r'^[a-z][a-z0-9_]*$')


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ModelError(f'{name}: forventer stabil ID (a-z, 0-9, _)')
    return value


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelError(f'{name}: forventer ikke-tom tekst')
    if len(value) > 300:
        raise ModelError(f'{name}: tekst er for lang')
    return value.strip()


def _fields(value: object, allowed: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ModelError(f'{label}: forventer JSON-objekt')
    extra = set(value) - allowed
    if extra:
        raise ModelError(f'{label}: ukjente felt: {", ".join(sorted(extra))}')
    return value


def _read(path: Path) -> dict:
    try:
        if path.stat().st_size > 2_000_000:
            raise ModelError(f'Modellfilen er for stor: {path.name}')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        if isinstance(exc, ModelError):
            raise
        raise ModelError(f'Kunne ikke lese JSON: {path.name}: {exc}') from exc
    return value


def _digest(value: dict) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def _format(data: dict, label: str) -> None:
    if type(data.get('format_version')) is not int or data['format_version'] != 1:
        raise ModelError(f'{label}: format_version ma vaere 1')


def _index(root: Path) -> dict:
    data = _fields(_read(root / 'index.json'),
                   {'format_version', 'id', 'label', 'modules', 'domains', 'taxonomies'},
                   'modellindeks')
    _format(data, 'modellindeks')
    _identifier(data.get('id'), 'modellindeks.id')
    _required_text(data.get('label'), 'modellindeks.label')
    for group in ('modules', 'domains'):
        items = data.get(group)
        if not isinstance(items, list) or not items:
            raise ModelError(f'modellindeks.{group} ma vaere en ikke-tom liste')
        ids = set()
        for item in items:
            item = _fields(item, {'id', 'path'}, f'modellindeks.{group}')
            item_id = _identifier(item.get('id'), f'modellindeks.{group}.id')
            # The only supported paths are these canonical in-repo subpaths.
            expected = ('common' if group == 'modules' else 'domains') + '/' + item_id + '.json'
            if item.get('path') != expected:
                raise ModelError(f'modellindeks: feil sti for {item_id}: {item.get("path")}')
            if item_id in ids:
                raise ModelError(f'modellindeks: duplikat {item_id}')
            ids.add(item_id)
    tax = data.get('taxonomies')
    if tax != 'taxonomies/kommunale_systemkategorier.json':
        raise ModelError('modellindeks: ukjent taksonomifil')
    return data


def list_domain_models(root: str | Path | None = None) -> list[dict]:
    """Return declared domains without reading any customer/database files."""
    root = Path(root) if root else MODEL_ROOT
    index = _index(root)
    out = []
    for ref in index['domains']:
        data = _domain(root / ref['path'], ref['id'])
        out.append({'id': data['id'], 'label': data['label'],
                    'category_code': data['category_code'], 'status': data['status']})
    return out


def _domain(path: Path, expected_id: str) -> dict:
    value = _fields(_read(path), {'format_version', 'id', 'label', 'category_code',
                                   'status', 'modules', 'description'}, 'domene')
    _format(value, 'domene')
    if _identifier(value.get('id'), 'domene.id') != expected_id:
        raise ModelError(f'Domene-ID stemmer ikke med filnavn: {expected_id}')
    _required_text(value.get('label'), 'domene.label')
    _required_text(value.get('category_code'), 'domene.category_code')
    if value.get('status') not in ('draft', 'pilot'):
        raise ModelError('Domene: forventer status draft/pilot (ikke normativt ferdig)')
    modules = value.get('modules')
    if not isinstance(modules, list) or not modules or len(modules) > 30:
        raise ModelError('domene.modules: forventer 1-30 moduler')
    if len(set(modules)) != len(modules):
        raise ModelError('domene.modules: duplikate modul-ID-er')
    for item in modules:
        _identifier(item, 'domene.modules')
    return value


def _module(path: Path, expected_id: str) -> dict:
    value = _fields(_read(path), {'format_version', 'id', 'label', 'description',
                                   'entities'}, 'modul')
    _format(value, 'modul')
    if _identifier(value.get('id'), 'modul.id') != expected_id:
        raise ModelError(f'Modul-ID stemmer ikke med filnavn: {expected_id}')
    _required_text(value.get('label'), 'modul.label')
    entities = value.get('entities')
    if not isinstance(entities, list) or not entities or len(entities) > 30:
        raise ModelError('modul.entities: forventer 1-30 fagbegreper')
    seen = set()
    for item in entities:
        item = _fields(item, {'id', 'label', 'aliases', 'description'}, 'fagbegrep')
        ent = _identifier(item.get('id'), 'fagbegrep.id')
        _required_text(item.get('label'), 'fagbegrep.label')
        if ent in seen:
            raise ModelError(f'Duplikat fagbegrep i modul: {ent}')
        seen.add(ent)
        aliases = item.get('aliases', [])
        if not isinstance(aliases, list) or len(aliases) > 30 or any(
                not isinstance(a, str) or not a.strip() or len(a) > 100 for a in aliases):
            raise ModelError(f'Fagbegrep {ent}: ugyldig aliasliste')
    return value


def load_domain_model(domain_id: str, root: str | Path | None = None) -> dict:
    """Resolve a domain and all shared modules, with traceable model hash."""
    root = Path(root) if root else MODEL_ROOT
    domain_id = _identifier(domain_id, 'domain_id')
    index = _index(root)
    known_domains = {r['id']: r for r in index['domains']}
    known_modules = {r['id']: r for r in index['modules']}
    if domain_id not in known_domains:
        raise ModelError(f'Ukjent fagomraade: {domain_id}')
    domain = _domain(root / known_domains[domain_id]['path'], domain_id)
    modules = []
    for module_id in domain['modules']:
        if module_id not in known_modules:
            raise ModelError(f'{domain_id}: ukjent modul {module_id}')
        modules.append(_module(root / known_modules[module_id]['path'], module_id))
    taxonomy = _fields(_read(root / index['taxonomies']),
                       {'format_version', 'source', 'primary_categories',
                        'municipal_categories'}, 'systemkategorier')
    _format(taxonomy, 'systemkategorier')
    cat = [c for c in taxonomy.get('municipal_categories', [])
           if c.get('code') == domain['category_code']]
    if len(cat) != 1:
        raise ModelError(f'{domain_id}: systemkategori {domain["category_code"]} mangler')
    payload = {'domain': domain, 'modules': modules,
               'taxonomy_category': cat[0]}
    return {**payload, 'model_sha256': _digest(payload)}


def _resource_file(value: str | Path, root: str | Path | None = None) -> Path:
    """Resolve a private adapter reference without path traversal or discovery."""
    requested = Path(value).expanduser()
    if requested.is_absolute():
        path = requested.resolve()
    else:
        if not root:
            raise ModelError('Relativ adaptersti krever en angitt fagressursmappe')
        base = Path(root).expanduser().resolve()
        path = (base / requested).resolve()
        if not path.is_relative_to(base):
            raise ModelError('Adapterstien peker utenfor fagressursmappen')
    if not path.is_file() or path.suffix.lower() != '.json':
        raise ModelError(f'Adapter-JSON finnes ikke: {path.name}')
    return path


def load_adapter(path: str | Path, *, resource_root: str | Path | None = None) -> tuple[dict, str]:
    """Read selected mapping from a private external JSON file; never execute SQL."""
    resolved = _resource_file(path, resource_root)
    adapter = _fields(_read(resolved),
                      {'format_version', 'id', 'label', 'domain_id', 'visibility',
                       'system_hint', 'standard_id', 'bindings', 'relations', 'description'}, 'adapter')
    _format(adapter, 'adapter')
    _identifier(adapter.get('id'), 'adapter.id')
    _identifier(adapter.get('domain_id'), 'adapter.domain_id')
    if adapter.get('standard_id') is not None:
        _identifier(adapter['standard_id'], 'adapter.standard_id')
    _required_text(adapter.get('label'), 'adapter.label')
    if adapter.get('visibility') not in ('internal', 'public', 'restricted'):
        raise ModelError('adapter.visibility: intern, offentlig eller begrenset')
    bindings = adapter.get('bindings')
    if not isinstance(bindings, list) or len(bindings) > 200:
        raise ModelError('adapter.bindings: ugyldig liste')
    seen = set()
    for entry in bindings:
        _fields(entry, {'entity_id', 'review_status', 'source', 'key', 'aliases',
                        'status_column', 'date_column', 'expected_count', 'distinct_metrics'}, 'adapter.binding')
        entity_id = _identifier(entry.get('entity_id'), 'adapter.binding.entity_id')
        if entity_id in seen:
            raise ModelError(f'Flere mappinger til samme fagbegrep: {entity_id}')
        seen.add(entity_id)
        if entry.get('review_status') not in ('approved', 'proposed'):
            raise ModelError(f'{entity_id}: review_status skal vaere approved/proposed')
        if entry['review_status'] == 'approved':
            if not entry.get('source') or not entry.get('key'):
                raise ModelError(f'{entity_id}: godkjent mapping krever kilde og nokkelfelt')
    relations = adapter.get('relations', [])
    if not isinstance(relations, list) or len(relations) > 300:
        raise ModelError('adapter.relations: ugyldig relasjonsliste')
    for relation in relations:
        _fields(relation, {'id', 'child', 'parent', 'child_columns',
                           'required', 'description', 'review_status'}, 'adapter.relation')
        if relation.get('review_status') not in ('approved', 'proposed'):
            raise ModelError('adapter.relation.review_status skal vaere approved/proposed')
    return adapter, _digest(adapter)


def resolve_qa_model(*, domain: str | None = None, adapter_file: str = '',
                     resource_root: str = '',
                     model_root: str | Path | None = None) -> tuple[dict, dict]:
    """Build a generic domain profile, using only approved adapter bindings.

    Unselected domain defaults to saksarkiv, unless an explicit adapter
    selects its own domain. No automatic system-specific approval occurs.
    """
    adapter_file = str(adapter_file or '').strip()
    resource_root = str(resource_root or '').strip()
    adapter = None
    digest = None
    if adapter_file:
        adapter, digest = load_adapter(adapter_file, resource_root=resource_root)
    selected = str(domain or '').strip()
    if not selected:
        selected = adapter['domain_id'] if adapter else 'saksarkiv'
    if adapter and selected != adapter['domain_id']:
        raise ModelError('Valgt fagmodell og adapterens domain_id er ulike')
    domain = selected
    model = load_domain_model(domain, model_root)
    carriers = []
    by_id = {}
    for module in model['modules']:
        for entity in module['entities']:
            entity_id = entity['id']
            if entity_id in by_id:
                raise ModelError(f'Fagbegrep er definert i flere moduler: {entity_id}')
            carrier = {'id': entity_id, 'label': entity['label'], 'source': None,
                       'key': [], 'aliases': list(entity.get('aliases', [])),
                       'description': entity.get('description', '')}
            carriers.append(carrier)
            by_id[entity_id] = carrier
    applied = pending = 0
    relations = []
    if adapter:
        for binding in adapter['bindings']:
            concept = binding['entity_id']
            if concept not in by_id:
                raise ModelError(f'Adapterens fagbegrep er ikke i domenet: {concept}')
            # Validate even proposed bindings to avoid smuggling unknown options.
            check = {'format_version': 1, 'id': 'adapter_check', 'label': 'adapter_check',
                     'carriers': [{'id': concept, 'label': concept,
                                   'source': binding.get('source'),
                                   'key': binding.get('key', []),
                                   **{x: binding[x] for x in ('status_column', 'date_column',
                                                              'expected_count', 'aliases', 'distinct_metrics') if x in binding}}],
                     'relations': []}
            try:
                validate_profile(check)
            except ProfileError as exc:
                raise ModelError(f'{concept}: {exc}') from exc
            if binding['review_status'] == 'proposed':
                pending += 1
                continue
            target = by_id[concept]
            for attr in ('source', 'key', 'status_column', 'date_column', 'expected_count', 'distinct_metrics'):
                if attr in binding:
                    target[attr] = deepcopy(binding[attr])
            # Aliases are stable domain knowledge, not proprietary field names.
            applied += 1
        for relation in adapter.get('relations', []):
            if relation['review_status'] == 'proposed':
                pending += 1
                continue
            rel = {k: deepcopy(v) for k, v in relation.items() if k != 'review_status'}
            relations.append(rel)
    profile = validate_profile({'format_version': 1,
                                'id': 'domain_' + domain,
                                'label': 'Fagmodell: ' + model['domain']['label'],
                                'description': 'Faglig utkast, ikke normativ godkjenning',
                                'carriers': carriers, 'relations': relations})
    context = {'mode': 'domain', 'domain_id': domain,
               'category_code': model['domain']['category_code'],
               'module_ids': [m['id'] for m in model['modules']],
               'model_sha256': model['model_sha256'],
               'adapter_id': adapter['id'] if adapter else None,
               'adapter_sha256': digest,
               'standard_id': adapter.get('standard_id') if adapter else None,
               'adapter_visibility': adapter['visibility'] if adapter else None,
               'bindings_applied': applied, 'bindings_pending': pending,
               'mapping_policy': 'only_explicitly_approved_bindings_execute'}
    return profile, context


def inspect_resource_library(root: str | Path | None) -> dict:
    """Check optional local template directories, never create or scan files.

    The folder can hold private Decom/KDRS templates and vendor adapters. No
    external reference files are bundled in the public application.
    """
    if not root or not str(root).strip():
        return {'configured': False}
    base = Path(root).expanduser()
    if not base.is_dir():
        raise ModelError(f'Fagressursmappe finnes ikke: {base}')
    return {'configured': True,
            'decom_templates': (base / 'templates' / 'decom').is_dir(),
            'kdrs_sok_og_vis_templates':
                (base / 'templates' / 'kdrs-sok-og-vis').is_dir(),
            'adapter_directory': (base / 'adapters').is_dir()}
