"""A4: shared system models + private adapter integration (synthetic data only)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from siard_workflow.core.content_qa.engine import run_content_qa
from siard_workflow.core.content_qa.model_catalog import (
    MODEL_ROOT, ModelError, list_domain_models, load_domain_model,
    load_adapter, inspect_resource_library, resolve_qa_model,
)
from siard_workflow.core.content_qa.__main__ import main as cli_main
from test_content_qa import synthetic_siard


SYNTHETIC_ADAPTER = {
    'format_version': 1,
    'id': 'synthetic_case_demo',
    'label': 'Kun syntetisk eksempel, ikke leverandormapping',
    'domain_id': 'saksarkiv',
    'visibility': 'internal',
    'system_hint': 'syntetisk',
    'bindings': [
        {'entity_id': 'case_file', 'review_status': 'approved',
         'source': {'schema': 'schema0', 'table': 'SAK'},
         'key': ['SAK_ID'], 'status_column': 'STATUS'},
        {'entity_id': 'journal_post', 'review_status': 'approved',
         'source': {'schema': 'schema0', 'table': 'JOURNALPOST'},
         'key': ['JP_ID'], 'date_column': 'JOURNAL_DATO'},
        {'entity_id': 'document_description', 'review_status': 'proposed',
         'source': {'schema': 'schema0', 'table': 'DOCUMENT'},
         'key': ['DOK_ID']},
    ],
    'relations': [
        {'id': 'journalpost_case', 'review_status': 'approved',
         'child': 'journal_post', 'parent': 'case_file',
         'child_columns': ['SAK_ID'], 'required': True},
        {'id': 'document_case_proposal', 'review_status': 'proposed',
         'child': 'document_description', 'parent': 'case_file',
         'child_columns': ['SAK_ID'], 'required': True},
    ],
}


class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def _adapter(self, content=None) -> Path:
        path = self.tmp / 'adapters' / 'synthetic.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(content or SYNTHETIC_ADAPTER), encoding='utf-8')
        return path

    def test_taxonomy_is_historical_working_reference(self):
        tax = json.loads((MODEL_ROOT / 'taxonomies/kommunale_systemkategorier.json')
                         .read_text(encoding='utf-8'))
        self.assertEqual(len(tax['primary_categories']), 9)
        self.assertEqual(len(tax['municipal_categories']), 20)
        self.assertEqual(tax['source']['filename'], '0000-kommune-elarkiv.xlsx')
        self.assertIn('not_normative', tax['source']['status'])
        self.assertEqual({x['code'] for x in tax['municipal_categories']},
                         {'1-01','1-02','1-03','1-04','2-05','3-19','3-20','4-06',
                          '4-07','4-08','4-09','4-10','5-11','5-12','5-13',
                          '6-14','6-15','6-16','6-17','6-18'})

    def test_all_pilot_domain_manifests_resolve(self):
        domains = list_domain_models()
        self.assertGreaterEqual(len(domains), 7)
        for entry in domains:
            model = load_domain_model(entry['id'])
            self.assertEqual(model['domain']['category_code'], entry['category_code'])
            self.assertTrue(model['modules'])
            self.assertEqual(len(model['model_sha256']), 64)
            self.assertEqual(model['domain']['status'], 'draft')

    def test_shared_modules_reused_without_copying(self):
        barnevern = load_domain_model('barnevern')
        skole = load_domain_model('skole')
        b = {m['id'] for m in barnevern['modules']}
        s = {m['id'] for m in skole['modules']}
        for common in ('client_registry', 'contact_info', 'document', 'person'):
            self.assertIn(common, b)
            self.assertIn(common, s)

    def test_default_is_generic_domain_not_old_template(self):
        profile, provenance = resolve_qa_model()
        self.assertEqual(profile['id'], 'domain_saksarkiv')
        self.assertEqual(provenance['mode'], 'domain')
        self.assertEqual(provenance['domain_id'], 'saksarkiv')
        self.assertTrue(all(c.get('source') is None for c in profile['carriers']))

    def test_domain_only_is_unmapped_and_never_claims_approval(self):
        profile, context = resolve_qa_model(domain='saksarkiv')
        self.assertEqual(context['domain_id'], 'saksarkiv')
        self.assertGreaterEqual(len(profile['carriers']), 10)
        self.assertTrue(all(c['source'] is None and c['key'] == []
                            for c in profile['carriers']))
        result = run_content_qa(synthetic_siard(self.tmp), profile, scan_rows=False)
        self.assertEqual(result['status'], 'DELVIS_KONTROLLERT')
        self.assertEqual(result['summary']['carriers_verified'], 0)

    def test_external_approved_bindings_only(self):
        file = self._adapter()
        profile, context = resolve_qa_model(adapter_file=str(file))
        mapped = {c['id']: c for c in profile['carriers']}
        self.assertEqual(context['domain_id'], 'saksarkiv')
        self.assertEqual(context['adapter_id'], 'synthetic_case_demo')
        self.assertEqual(context['bindings_applied'], 2)
        self.assertEqual(context['bindings_pending'], 2)
        self.assertEqual(len(context['adapter_sha256']), 64)
        self.assertEqual(mapped['case_file']['source']['table'], 'SAK')
        self.assertEqual(mapped['document_description']['source'], None)
        self.assertEqual(len(profile['relations']), 1)
        self.assertNotIn(str(file), json.dumps(context))
        self.assertNotIn('SAK_ID', json.dumps(context))

    def test_approved_bindings_work_in_generic_siard_qa(self):
        file = self._adapter()
        profile, context = resolve_qa_model(domain='saksarkiv',
                                            adapter_file=str(file))
        source = synthetic_siard(self.tmp)
        unchanged = source.read_bytes()
        result = run_content_qa(source, profile)
        self.assertEqual(result['status'], 'DELVIS_KONTROLLERT')
        self.assertEqual(result['summary']['carriers_verified'], 2)
        self.assertEqual(result['summary']['relations_verified'], 1)
        self.assertEqual(source.read_bytes(), unchanged)
        self.assertEqual({x['id'] for x in result['carriers'] if x['status'] == 'OK'},
                         {'case_file', 'journal_post'})
        self.assertFalse(any(x['id'] == 'document_description' and x['status'] == 'OK'
                             for x in result['carriers']))

    def test_relative_adapter_requires_resource_root(self):
        self._adapter()
        with self.assertRaises(ModelError):
            resolve_qa_model(adapter_file='adapters/synthetic.json')
        profile, context = resolve_qa_model(
            resource_root=str(self.tmp), adapter_file='adapters/synthetic.json')
        self.assertEqual(context['adapter_id'], 'synthetic_case_demo')
        self.assertTrue(profile['carriers'])

    def test_traversal_blocked(self):
        self._adapter()
        with self.assertRaises(ModelError):
            load_adapter('../adapters/synthetic.json', resource_root=self.tmp)
        with self.assertRaises(ModelError):
            load_domain_model('../saksarkiv')

    def test_wrong_domain_and_removed_profile_option_rejected(self):
        file = self._adapter()
        with self.assertRaises(ModelError):
            resolve_qa_model(domain='barnevern', adapter_file=str(file))
        with self.assertRaises(TypeError):
            resolve_qa_model(profile_file='old.json')

    def test_unknown_module_does_not_silently_disappear(self):
        other = self.tmp / 'models'
        shutil.copytree(MODEL_ROOT, other)
        p = other / 'domains' / 'saksarkiv.json'
        data = json.loads(p.read_text(encoding='utf-8'))
        data['modules'].append('mystery_system')
        p.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ModelError):
            load_domain_model('saksarkiv', other)

    def test_unknown_adapter_entities_rejected(self):
        data = deepcopy(SYNTHETIC_ADAPTER)
        data['bindings'][0]['entity_id'] = 'not_in_model'
        with self.assertRaises(ModelError):
            resolve_qa_model(adapter_file=str(self._adapter(data)))

    def test_approved_binding_requires_key_and_source(self):
        data = deepcopy(SYNTHETIC_ADAPTER)
        data['bindings'][0]['key'] = []
        with self.assertRaises(ModelError):
            resolve_qa_model(adapter_file=str(self._adapter(data)))
        data['bindings'][0]['key'] = ['SAK_ID']
        del data['bindings'][0]['source']
        with self.assertRaises(ModelError):
            resolve_qa_model(adapter_file=str(self._adapter(data)))

    def test_unverified_relation_is_not_executed(self):
        data = deepcopy(SYNTHETIC_ADAPTER)
        data['relations'][0]['review_status'] = 'proposed'
        _, context = resolve_qa_model(adapter_file=str(self._adapter(data)))
        p, _ = resolve_qa_model(adapter_file=str(self._adapter(data)))
        self.assertEqual(len(p['relations']), 0)
        self.assertEqual(context['bindings_pending'], 3)

    def test_reject_executable_rule_fields(self):
        data = deepcopy(SYNTHETIC_ADAPTER)
        data['sql'] = 'DELETE FROM database'
        with self.assertRaises(ModelError):
            resolve_qa_model(adapter_file=str(self._adapter(data)))
        data = deepcopy(SYNTHETIC_ADAPTER)
        data['bindings'][0]['python'] = 'exec(1)'
        with self.assertRaises(ModelError):
            resolve_qa_model(adapter_file=str(self._adapter(data)))

    def test_resource_library_is_read_only_and_optional(self):
        self.assertEqual(inspect_resource_library(''), {'configured': False})
        self.assertFalse((self.tmp / 'templates').exists())
        state = inspect_resource_library(self.tmp)
        self.assertTrue(state['configured'])
        self.assertFalse(state['decom_templates'])
        self.assertFalse((self.tmp / 'templates').exists())
        (self.tmp / 'templates' / 'decom').mkdir(parents=True)
        state = inspect_resource_library(self.tmp)
        self.assertTrue(state['decom_templates'])
        with self.assertRaises(ModelError):
            inspect_resource_library(self.tmp / 'missing')

    def test_cli_model_listing_no_archive_required(self):
        self.assertEqual(cli_main(['--list-domains']), 0)

    def test_operation_a4_partial_with_domain_only(self):
        from siard_workflow.core.context import WorkflowContext
        from siard_workflow.operations.content_qa_operation import ContentQAOperation
        source = synthetic_siard(self.tmp)
        ctx = WorkflowContext(siard_path=source)
        ctx.metadata['log_dir'] = str(self.tmp / 'logs')
        result = ContentQAOperation(domain_profile='saksarkiv', scan_rows=False).run(ctx)
        self.assertTrue(result.success)
        self.assertEqual(result.data['qa_status'], 'DELVIS_KONTROLLERT')
        self.assertEqual(result.data['qa_domain_id'], 'saksarkiv')
        self.assertEqual(result.data['qa_bindings_approved'], 0)
        report = json.loads(Path(result.data['qa_report_json']).read_text('utf-8'))
        self.assertEqual(report['model_context']['domain_id'], 'saksarkiv')
        self.assertEqual(report['source_type'], 'siard_fil')
        self.assertFalse(report['resource_library']['configured'])
        self.assertTrue(Path(result.data['qa_report_pdf']).is_file())

    def test_operation_a4_external_adapter_does_not_modify_source(self):
        from siard_workflow.core.context import WorkflowContext
        from siard_workflow.operations.content_qa_operation import ContentQAOperation
        source = synthetic_siard(self.tmp)
        before = source.read_bytes()
        adapter = self._adapter()
        ctx = WorkflowContext(siard_path=source)
        ctx.metadata['log_dir'] = str(self.tmp / 'logs')
        op = ContentQAOperation(adapter_file='adapters/synthetic.json',
                                resources_root=str(self.tmp))
        result = op.run(ctx)
        self.assertTrue(result.success)  # QA remains partially checked.
        self.assertEqual(result.data['qa_status'], 'DELVIS_KONTROLLERT')
        self.assertEqual(result.data['qa_bindings_approved'], 2)
        self.assertEqual(result.data['qa_bindings_pending'], 2)
        self.assertEqual(result.data['qa_carriers_verified'], 2)
        self.assertEqual(result.data['qa_relations_verified'], 1)
        self.assertEqual(source.read_bytes(), before)
        report = Path(result.data['qa_report_json']).read_text('utf-8')
        self.assertIn('synthetic_case_demo', report)
        self.assertNotIn(str(adapter.resolve()), report)
        self.assertIn('adapter_sha256', report)

    def test_operation_wrong_domain_mapping_returns_fail_not_green(self):
        from siard_workflow.core.context import WorkflowContext
        from siard_workflow.operations.content_qa_operation import ContentQAOperation
        source = synthetic_siard(self.tmp)
        ctx = WorkflowContext(siard_path=source)
        op = ContentQAOperation(domain_profile='barnevern',
                                adapter_file=str(self._adapter()))
        result = op.run(ctx)
        self.assertFalse(result.success)
        self.assertIn('ulike', result.message)

    def test_operation_a4_parameters_roundtrip(self):
        from siard_workflow.operations.content_qa_operation import ContentQAOperation
        opts = {'domain_profile':'barnevern',
                'resources_root':r'F:\arkiv-fagressurser',
                'adapter_file':r'F:\arkiv-fagressurser\adapters\familia.json'}
        saved = json.loads(json.dumps(ContentQAOperation(**opts).params))
        restored = ContentQAOperation(**saved)
        for key,value in opts.items():
            self.assertEqual(restored.params[key], value)


if __name__ == '__main__':
    unittest.main()
