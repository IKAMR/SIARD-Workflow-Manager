"""Compatibility messages for vendor-specific a6 QA settings.

New generic QA profiles must never generate vendor adapter proposals implicitly.
The obsolete option remains detectable so old .siardwf projects are not silently
misinterpreted; their settings can be retained without taking vendor actions.
"""
from __future__ import annotations


def unsupported_legacy_options(params: dict) -> list[str]:
    warnings = []
    if params.get('propose_ephorte_noark4_adapter'):
        warnings.append(
            'A7: gammelt ePhorte/Noark 4-adapterforslag er deaktivert. '
            'Generisk QA produserer ingen systemspesifikke adapterfiler; '
            'bruk en separat, eksplisitt adaptergenerator.'
        )
    return warnings
