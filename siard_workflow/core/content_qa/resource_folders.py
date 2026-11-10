"""Separate user-selected libraries for SIARD templates and external adapters.

The Decom setting keeps the historical SIARDMapper config key
`json_template_dir`; the other two paths are recorded separately alongside
config.json. Never bundle or auto-discover proprietary mapping files.
"""
from __future__ import annotations

import json
from pathlib import Path

from app_paths import data_dir
from settings import get_config, save_config

RESOURCE_FOLDERS_FILE = data_dir() / 'resource_folders.json'
_KDRS_KEY = 'kdrs_sok_vis_dir'
_ADAPTER_KEY = 'system_adapter_dir'


class ResourceFolderError(ValueError):
    """Invalid local resource-folder setting."""


def load_resource_folders(*, config_file: Path | None = None) -> dict[str, str]:
    """Return the independent directory settings without scanning any library."""
    result = {'decom_templates_dir': str(get_config('json_template_dir') or ''),
              _KDRS_KEY: '', _ADAPTER_KEY: ''}
    location = Path(config_file) if config_file is not None else RESOURCE_FOLDERS_FILE
    if not location.exists():
        return result
    try:
        obj = json.loads(location.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ResourceFolderError(f'Kunne ikke lese ressursmappeoppsett {location}: {exc}') from exc
    if not isinstance(obj, dict) or obj.get('format_version') != 1:
        raise ResourceFolderError('Ugyldig format i resource_folders.json (krever versjon 1)')
    for key in (_KDRS_KEY, _ADAPTER_KEY):
        val = obj.get(key, '')
        if not isinstance(val, str):
            raise ResourceFolderError(f'{key} skal være tekst')
        result[key] = val.strip()
    return result


def validate_resource_folders(values: dict[str, str]) -> dict[str, str]:
    """Validate directory references without creating or copying folder content."""
    result = {}
    for key in ('decom_templates_dir', _KDRS_KEY, _ADAPTER_KEY):
        val = values.get(key, '')
        if not isinstance(val, str):
            raise ResourceFolderError(f'{key} må være en mappesti')
        val = val.strip()
        if val and not Path(val).expanduser().is_dir():
            raise ResourceFolderError(f'Mappen finnes ikke eller er utilgjengelig ({key}): {val}')
        result[key] = val
    return result


def save_resource_folders(values: dict[str, str], *,
                          config_file: Path | None = None) -> Path:
    """Atomically save local folder choices; preserve Decom's config.json key."""
    clean = validate_resource_folders(values)
    location = Path(config_file) if config_file is not None else RESOURCE_FOLDERS_FILE
    location.parent.mkdir(parents=True, exist_ok=True)
    payload = {'format_version': 1,
               _KDRS_KEY: clean[_KDRS_KEY],
               _ADAPTER_KEY: clean[_ADAPTER_KEY]}
    temp = location.with_name(location.name + '.tmp')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
        temp.replace(location)
    finally:
        if temp.exists():
            temp.unlink()
    # Decom mapping remains the same global SIARDMapper setting.
    if clean['decom_templates_dir'] != str(get_config('json_template_dir') or ''):
        save_config({'json_template_dir': clean['decom_templates_dir']})
        if str(get_config('json_template_dir') or '') != clean['decom_templates_dir']:
            raise ResourceFolderError('Kunne ikke lagre Decom-mappen i config.json')
    return location


def inspect_resource_folders(values: dict[str, str]) -> dict:
    """Return boolean availability only; never auto-import KDRS templates."""
    return {
        'configured': any(values.values()),
        'decom_templates': bool(values.get('decom_templates_dir')),
        'kdrs_sok_og_vis_templates': bool(values.get(_KDRS_KEY)),
        'adapter_directory': bool(values.get(_ADAPTER_KEY)),
        'kdrs_templates_used_for_qa': False,
        'automatic_adapter_approval': False,
    }
