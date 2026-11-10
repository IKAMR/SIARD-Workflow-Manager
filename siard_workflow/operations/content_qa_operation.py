"""Workflow operation for read-only SIARD content QA."""
from __future__ import annotations

from pathlib import Path

from siard_workflow.core.base_operation import BaseOperation, OperationResult
from siard_workflow.core.context import WorkflowContext
from siard_workflow.core.content_qa import run_content_qa
from siard_workflow.core.content_qa.reporting import write_qa_reports
from siard_workflow.core.content_qa.model_catalog import (
    resolve_qa_model, load_adapter,
)
from siard_workflow.core.content_qa.resource_folders import (
    load_resource_folders, inspect_resource_folders,
)
from siard_workflow.core.content_qa.domain_metrics import build_domain_metrics
from siard_workflow.core.content_qa.migration_a6 import unsupported_legacy_options
from siard_workflow.core.content_qa.adapter_review import review_adapter_against_catalog


class ContentQAOperation(BaseOperation):
    operation_id = 'content_qa'
    label = 'Innholdskontroll (QA / informasjonsbærere)'
    description = (
        'Skrivebeskyttet analyse av SIARD-tabeller, radantall og faglige '
        'informasjonsbærere etter JSON-mal. Dokumenterer avvik, manglende '
        'kartlegging og relasjonsfeil. Lager JSON, CSV og PDF. '
        'Foreslår tabell-/nøkkelkoblinger og leser deklarerte fremmednøkler '
        'fra SIARD-metadata uten å godkjenne forslagene automatisk. '
        'Kildevalg: automatisk, utpakket SIARD eller SIARD-fil. '
        'Kan kjøres før eller etter Pakk sammen SIARD. '
        'Systemspesifikke kartlegginger leveres kun via eksplisitte eksterne adaptere.'
    )
    category = 'Innhold'
    status = 1  # Pilot/beta, not a complete validated QA product.
    produces_siard = False
    requires_unpack = False
    modifies_content = False
    halt_on_failure = False

    default_params = {
        'source_mode': 'Automatisk',
        'unpacked_dir': '',
        'domain_profile': 'saksarkiv',
        'adapter_file': '',
        'resources_root': '',
        'scan_rows': True,
        'check_metadata_pk': True,
    }

    SOURCE_MODES = ('Automatisk', 'Utpakket SIARD', 'SIARD-fil')

    def _select_source(self, ctx: WorkflowContext) -> tuple[Path, str, str, str]:
        """Velg faktisk datakilde uten å endre den.

        Returnerer (sti, kildetype, brukerens valg, opprinnelse).
        En eksplisitt mappe må være gyldig; vi faller aldri stille tilbake
        til en annen kilde dersom operatøren har oppgitt feil mappe.
        """
        mode = str(self.params.get('source_mode') or 'Automatisk').strip()
        if mode not in self.SOURCE_MODES:
            raise ValueError(f'Ukjent QA-kildevalg: {mode!r}')

        raw_dir = str(self.params.get('unpacked_dir') or '').strip()
        selected_folder = Path(raw_dir).expanduser() if raw_dir else None
        workflow_folder = (Path(ctx.extracted_path)
                           if ctx.extracted_path is not None else None)

        def valid_folder(folder: Path, *, explicit: bool) -> bool:
            if not folder.is_dir():
                if explicit or mode == 'Utpakket SIARD':
                    raise FileNotFoundError(f'Utpakket SIARD-mappe finnes ikke: {folder}')
                return False
            if not ((folder / 'header' / 'metadata.xml').is_file()
                    or (folder / 'metadata.xml').is_file()):
                raise ValueError(
                    f'Mappen er ikke en utpakket SIARD (mangler metadata.xml): {folder}')
            return True

        if mode != 'SIARD-fil':
            if selected_folder is not None:
                valid_folder(selected_folder, explicit=True)
                return selected_folder, 'utpakket_siard', mode, 'Manuelt valgt mappe'
            if workflow_folder is not None and valid_folder(workflow_folder, explicit=False):
                return workflow_folder, 'utpakket_siard', mode, 'Arbeidsflytens utpakking'
            # Direkte API-kjøring kan angi en utpakket mappe som aktiv kilde.
            active_source = Path(ctx.siard_path)
            if active_source.is_dir() and valid_folder(active_source, explicit=True):
                return active_source, 'utpakket_siard', mode, 'Aktiv utpakket SIARD-mappe'
            if mode == 'Utpakket SIARD':
                raise ValueError(
                    'Utpakket SIARD er valgt, men ingen mappe er tilgjengelig. '
                    'Legg Innholdskontroll etter «Pakk ut SIARD», eller velg en '
                    'utpakket mappe i operasjonens innstillinger.')

        archive = Path(ctx.siard_path)
        if not archive.is_file():
            raise FileNotFoundError(f'SIARD-fil finnes ikke: {archive}')
        return archive, 'siard_fil', mode, 'Aktiv SIARD-fil i arbeidsflyten'

    def run(self, ctx: WorkflowContext) -> OperationResult:
        log = ctx.metadata.get('file_logger')
        progress_cb = ctx.metadata.get('progress_cb')

        def message(msg: str, level: str = 'info'):
            if log:
                log.log(msg, 'success' if level == 'ok' else level)
            if progress_cb:
                progress_cb('log', msg=msg, level=level)

        try:
            source, source_type, source_mode, source_origin = self._select_source(ctx)
            folders = load_resource_folders()
            # The dedicated system-adapter directory takes precedence over the
            # old a8 `resources_root`, retained for earlier .siardwf files.
            resources_root = (folders['system_adapter_dir']
                              or str(self.params.get('resources_root') or '').strip())
            library = inspect_resource_folders(folders)
            profile, model_context = resolve_qa_model(
                domain=str(self.params.get('domain_profile') or 'saksarkiv'),
                adapter_file=str(self.params.get('adapter_file') or ''),
                resource_root=resources_root,
            )
            for warning in unsupported_legacy_options(self.params):
                message('  ' + warning, 'warn')
            if library['configured']:
                message('  Ressursmapper: Decom=' +
                        ('valgt' if folders['decom_templates_dir'] else 'ikke satt') +
                        '; KDRS Søk & Vis=' +
                        ('valgt' if folders['kdrs_sok_vis_dir'] else 'ikke satt') +
                        '; systemadaptere=' +
                        ('valgt' if resources_root else 'ikke satt') +
                        ' (ingen automatisk KDRS-import)')
            if model_context['mode'] == 'domain':
                category = model_context.get('category_code') or ''
                domain_label = str(profile.get('label') or model_context['domain_id']).removeprefix('Fagmodell: ')
                message('  Fagmodell: ' + (category + ' ' if category else '') + domain_label +
                        f'; moduler: {len(model_context["module_ids"])}; '
                        f'godkjente kartlegginger: {model_context["bindings_applied"]}; '
                        f'forslag som ikke aktiveres: {model_context["bindings_pending"]}')
            scan = bool(self.params.get('scan_rows', True))
            stop_event = ctx.metadata.get('stop_event')
            source_label = ('Utpakket SIARD' if source_type == 'utpakket_siard'
                            else 'SIARD-fil')
            message(f'  Innholdskontroll: {source_label} ({source_mode}); '
                    f'profil: {profile["id"]}')
            message(f'  QA-kilde ({source_origin}): {source}')
            result = run_content_qa(
                source, profile, scan_rows=scan,
                check_metadata_pk=bool(self.params.get('check_metadata_pk', True)),
                on_progress=lambda info: message('  QA: ' + info),
                should_stop=stop_event.is_set if stop_event else None,
                temp_dir=ctx.metadata.get('temp_dir'),
            )
            # Rapporter beholdes utenfor SIARD-arbeidsmappen (den kan slettes
            # av repack-steget). Filnavn følger opprinnelig SIARD, ikke temp-mappen.
            result['source_type'] = source_type
            result['source_selection'] = source_mode
            result['source_origin'] = source_origin
            result['input_siard_name'] = Path(ctx.siard_path).name
            result['model_context'] = model_context
            if model_context.get('mode') == 'domain':
                result['system_category'] = {
                    'code': model_context.get('category_code'),
                    'label': str(profile.get('label') or '').removeprefix('Fagmodell: '),
                    'domain_id': model_context['domain_id'],
                }
            # A8: review the selected, explicit adapter against the real catalog.
            # This does not enable or approve any proposed bindings.
            adapter_ref = str(self.params.get('adapter_file') or '').strip()
            if adapter_ref:
                adapter, _ = load_adapter(adapter_ref, resource_root=resources_root)
                result['adapter_review'] = review_adapter_against_catalog(
                    adapter, result['catalog'])
                check = result['adapter_review']['summary']
                message('  Adapter mot metadata: '
                        f'{check["bindings_metadata_match"]}/{check["bindings"]} '
                        'bindinger med deklarert PK; '
                        f'{check["relations_type_review"]} relasjoner trenger typegjennomgang; '
                        'INGEN automatisk faglig godkjenning')
            result['resource_library'] = library
            result['resource_folders_configured'] = {
                'decom_templates': bool(folders['decom_templates_dir']),
                'kdrs_sok_og_vis_templates': bool(folders['kdrs_sok_vis_dir']),
                'system_adapters': bool(resources_root),
            }
            result['semantic_results'] = build_domain_metrics(result, model_context)
            output_dir = Path(ctx.metadata.get('log_dir') or Path(ctx.siard_path).parent)
            message(f'  QA-rapportmappe (uavhengig av prosjektfil): {output_dir}')
            paths = write_qa_reports(result, output_dir, Path(ctx.siard_path).stem)
            summary = result['summary']
            data = {
                'qa_status': result['status'],
                'qa_execution_status': 'FULLFORT',
                'qa_source_type': source_type,
                'qa_source_mode': source_mode,
                'qa_source_origin': source_origin,
                'qa_source_name': source.name,
                'qa_tables': summary['tables'],
                'qa_tables_verified': summary['tables_verified'],
                'qa_tables_with_errors': summary['tables_with_errors'],
                'qa_pk_verified': summary['pk_verified'],
                'qa_pk_with_errors': summary['pk_with_errors'],
                'qa_carriers': summary['carriers'],
                'qa_carriers_verified': summary['carriers_verified'],
                'qa_carriers_unverified': summary['carriers_unverified'],
                'qa_carriers_with_errors': summary['carriers_with_errors'],
                'qa_relations_verified': summary['relations_verified'],
                'qa_profile_id': result['profile_id'],
                'qa_domain_id': model_context['domain_id'],
                'qa_category_code': model_context.get('category_code'),
                'qa_category_label': result.get('system_category', {}).get('label'),
                'qa_model_sha256': model_context['model_sha256'],
                'qa_adapter_id': model_context['adapter_id'],
                'qa_adapter_sha256': model_context['adapter_sha256'],
                'qa_bindings_approved': model_context['bindings_applied'],
                'qa_bindings_pending': model_context['bindings_pending'],
                'qa_standard_id': model_context.get('standard_id'),
                'qa_semantic_metrics_csv': paths.get('semantic_metrics_csv'),
                'qa_report_pdf': paths['pdf'],
                'qa_report_json': paths['json'],
                'qa_tables_csv': paths['tables_csv'],
                'qa_carriers_csv': paths['carriers_csv'],
                'qa_findings_csv': paths['findings_csv'],
                'qa_mapping_csv': paths['mapping_csv'],
                'qa_foreign_keys_csv': paths['foreign_keys_csv'],
                'qa_relation_proposals_csv': paths['relation_proposals_csv'],
                'qa_mapping_json': paths['mapping_json'],
                'qa_adapter_review_bindings_csv': paths.get('adapter_review_bindings_csv'),
                'qa_adapter_review_relations_csv': paths.get('adapter_review_relations_csv'),
                'qa_discovery_carriers_with_candidates': summary['discovery_carriers_with_candidates'],
                'qa_discovery_declared_foreign_keys': summary['discovery_declared_foreign_keys'],
                'qa_discovery_relation_proposals': summary['discovery_relation_proposals'],
            }
            message(f'  QA-rapport: {Path(paths["pdf"]).name}', 'ok')
            message(f'  Kartlegging: {summary["discovery_carriers_with_candidates"]}/'
                    f'{summary["carriers"]} fagbegreper med tabellforslag; '
                    f'{summary["discovery_declared_foreign_keys"]} fremmednøkler fra metadata; '
                    f'{summary["discovery_relation_proposals"]} navnebaserte relasjonsforslag')
            message(f'  QA-status: {result["status"]}; '
                    f'{summary["tables_verified"]}/{summary["tables"]} tabeller; '
                    f'{summary["carriers_verified"]}/{summary["carriers"]} informasjonsbærere',
                    'warn' if result['status'] != 'GODKJENT' else 'ok')
            verdict = (f'QA {result["status"]}: {summary["tables_verified"]}/'
                       f'{summary["tables"]} tabeller, '
                       f'{summary["carriers_verified"]}/{summary["carriers"]} informasjonsbærere')
            if result['status'] == 'AVVIK':
                return self._fail(verdict + '; se PDF/CSV', data)
            if result['status'] == 'DELVIS_KONTROLLERT':
                # Execution completed; QA approval is still explicitly withheld.
                return self._ok(data, verdict +
                                '; kontroll gjennomfort - IKKE FAGLIG GODKJENT; se PDF/CSV')
            return self._ok(data, verdict + '; se PDF/CSV')
        except Exception as exc:
            # Preserve failure information instead of showing a green step if
            # a table, a temporary index or the PDF report could not be built.
            detail = f'{type(exc).__name__}: {exc}'
            message('  QA kunne ikke fullføres: ' + detail, 'warn')
            return self._fail('QA kunne ikke fullføres: ' + detail)
