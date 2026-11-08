"""CLI: python -m siard_workflow.core.content_qa [file.siard] [options]."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .engine import run_content_qa
from .model_catalog import (ModelError, list_domain_models,
                            resolve_qa_model, inspect_resource_library)
from .reporting import write_qa_reports
from .semantic_results import build_noark4_metrics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Skrivebeskyttet SIARD innholdskontroll')
    parser.add_argument('siard', nargs='?', help='SIARD ZIP-fil eller utpakket SIARD-mappe')
    parser.add_argument('--domain', default=None,
                        help='Generisk fagmodell, f.eks. saksarkiv, barnevern, skole')
    parser.add_argument('--adapter', default='',
                        help='Valgfri ekstern, manuelt gjennomgatt systemadapter i JSON')
    parser.add_argument('--resources-root', default='',
                        help='Eksternt fagressursbibliotek (Decom, KDRS og adaptere)')
    parser.add_argument('--list-domains', action='store_true',
                        help='Vis tilgjengelige generiske fagmodeller og avslutt')
    parser.add_argument('--out', default='', help='Utmappe for CSV, JSON og PDF')
    parser.add_argument('--skip-metadata-pk', action='store_true',
                        help='Ikke kontroller deklarerte primaernokler')
    parser.add_argument('--metadata-only', '--kartlegging', dest='metadata_only',
                        action='store_true',
                        help='Les kun katalog og lag kartleggingsforslag; ikke radskann')
    args = parser.parse_args(argv)
    try:
        if args.list_domains:
            for item in list_domain_models():
                print(f"{item['id']:<18} {item['category_code']:<5} "
                      f"{item['label']} ({item['status']})")
            return 0
        if not args.siard:
            parser.error('SIARD-sti mangler (eller bruk --list-domains)')
        library = inspect_resource_library(args.resources_root)
        profile, model_context = resolve_qa_model(
            domain=args.domain, adapter_file=args.adapter,
            resource_root=args.resources_root,
        )
        source = Path(args.siard)
        result = run_content_qa(source, profile, scan_rows=not args.metadata_only,
                                check_metadata_pk=not args.skip_metadata_pk,
                                on_progress=lambda msg: print(msg, flush=True))
        result['model_context'] = model_context
        result['semantic_results'] = build_noark4_metrics(result, model_context)
        result['resource_library'] = library
        result['input_siard_name'] = source.name
        output = Path(args.out) if args.out else source.parent
        paths = write_qa_reports(result, output, source.stem)
        print(f'QA-status: {result["status"]}')
        for k, val in paths.items():
            print(f'  {k}: {val}')
        return {'GODKJENT': 0, 'DELVIS_KONTROLLERT': 2,
                'AVVIK': 3}[result['status']]
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        print(f'QA-feil: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
