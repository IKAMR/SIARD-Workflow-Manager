"""a8: vendor-independent domain model and external adapter review.

All database objects in these tests are invented. No named commercial
system, private production schema, SIARD content, or external folder needed.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from siard_workflow.core.content_qa.model_catalog import (
    MODEL_ROOT, list_domain_models, load_domain_model, load_adapter,
    resolve_qa_model,
)
from siard_workflow.core.content_qa.adapter_review import review_adapter_against_catalog
from siard_workflow.core.content_qa.reporting import write_qa_reports


def synthetic_adapter():
    return {
        'format_version': 1,
        'id': 'synthetic_social_register',
        'label': 'Synthetic social-service adapter - test only',
        'domain_id': 'sosialtjeneste',
        'category_code': '6-18',
        'visibility': 'internal',
        'bindings': [
            {'entity_id': 'person', 'review_status': 'proposed',
             'source': {'schema': 'TEST', 'table': 'People'}, 'key': ['ID']},
            {'entity_id': 'social_application', 'review_status': 'proposed',
             'source': {'schema': 'TEST', 'table': 'Applications'}, 'key': ['ID']},
            {'entity_id': 'social_decision', 'review_status': 'proposed',
             'source': {'schema': 'TEST', 'table': 'Decisions'}, 'key': ['ID']},
            {'entity_id': 'intervention', 'review_status': 'proposed',
             'source': {'schema': 'TEST', 'table': 'Measures'}, 'key': ['ID']},
        ],
        'relations': [
            {'id': 'decision_application', 'child': 'social_decision',
             'parent': 'social_application', 'child_columns': ['APPLICATION_ID'],
             'review_status': 'proposed', 'required': False},
            {'id': 'measure_person', 'child': 'intervention',
             'parent': 'person', 'child_columns': ['PERSON_ID'],
             'review_status': 'proposed', 'required': False},
        ],
    }


def synthetic_catalog():
    def table(name, fields):
        return {
            'schema': 'TEST', 'table': name,
            'primary_key': ['ID'], 'metadata_rows': 3, 'actual_rows': None,
            'columns': [{'name': n, 'sql_type': dtype, 'nullable': 'true'}
                        for n, dtype in fields],
        }
    return [
        table('People', [('ID', 'INT')]),
        table('Applications', [('ID', 'INT')]),
        table('Decisions', [('ID', 'INT'), ('APPLICATION_ID', 'FLOAT(53)')]),
        table('Measures', [('ID', 'INT'), ('PERSON_ID', 'INT')]),
    ]


class SocialRegisterA8Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.adapter_file = self.root / 'synthetic_adapter.json'
        self.adapter_file.write_text(json.dumps(synthetic_adapter()), encoding='utf-8')
        self.adapter, self.adapter_sha = load_adapter(self.adapter_file)

    def test_authoritative_20_categories_and_combined_code(self):
        tax = json.loads((MODEL_ROOT / 'taxonomies/kommunale_systemkategorier.json')
                         .read_text(encoding='utf-8'))
        self.assertEqual(len(tax['primary_categories']), 9)
        self.assertEqual(len(tax['municipal_categories']), 20)
        item = next(c for c in tax['municipal_categories'] if c['code'] == '6-18')
        self.assertEqual((item['primary_code'], item['subcode'], item['label']),
                         ('6', '18', 'Sosialtjeneste'))
        self.assertIn('sosialtjeneste', {d['id'] for d in list_domain_models()})

    def test_generic_module_has_no_vendor_schema_fields(self):
        model = load_domain_model('sosialtjeneste')
        self.assertEqual(model['domain']['category_code'], '6-18')
        self.assertIn('social_register', model['domain']['modules'])
        ents = {e['id']: e for module in model['modules'] for e in module['entities']}
        for key in ('social_application', 'social_decision', 'social_plan',
                    'social_journal_entry', 'social_transaction', 'social_income_expense'):
            self.assertIn(key, ents)
        self.assertNotIn('vedtak', ents['intervention']['aliases'])
        self.assertIn('vedtak', ents['social_decision']['aliases'])
        self.assertNotIn('inntutg', ents['social_income_expense']['aliases'])
        self.assertNotIn('trans', ents['social_transaction']['aliases'])
        module = next(m for m in model['modules'] if m['id'] == 'social_register')
        for item in module['entities']:
            self.assertNotIn('source', item)
            self.assertNotIn('key', item)

    def test_repo_contains_no_system_specific_adapter_json(self):
        # The application must not ship mapping files for named systems.
        repo_root = Path(__file__).resolve().parents[1]
        embedded = list((repo_root / 'docs' / 'adapters').glob('*.json'))
        self.assertEqual(embedded, [],
                         'Flytt systemspesifikke adaptere ut av SWM-repositoryet')

    def test_proposed_external_adapter_is_not_auto_approved(self):
        profile, ctx = resolve_qa_model(domain='sosialtjeneste',
                                        adapter_file=str(self.adapter_file))
        self.assertEqual(ctx['category_code'], '6-18')
        self.assertEqual(ctx['bindings_applied'], 0)
        self.assertEqual(ctx['bindings_pending'], 6)
        self.assertEqual(len(ctx['adapter_sha256']), 64)
        self.assertFalse(profile['relations'])
        self.assertTrue(all(c.get('source') is None for c in profile['carriers']))

    def test_system_adapter_cannot_be_selected_from_repo_tree(self):
        from siard_workflow.core.content_qa.model_catalog import ModelError
        # The file need only exist inside repo: the path policy is checked
        # before interpreting its contents as an adapter.
        bundled_model = MODEL_ROOT / 'domains' / 'sosialtjeneste.json'
        with self.assertRaises(ModelError) as cm:
            load_adapter(bundled_model)
        self.assertIn('utenfor SWM-repositoryet', str(cm.exception))

    def test_wrong_category_code_is_rejected(self):
        from siard_workflow.core.content_qa.model_catalog import ModelError
        malformed = synthetic_adapter()
        malformed['category_code'] = '6-17'
        self.adapter_file.write_text(json.dumps(malformed), encoding='utf-8')
        with self.assertRaises(ModelError):
            resolve_qa_model(domain='sosialtjeneste',
                             adapter_file=str(self.adapter_file))

    def test_adapter_metadata_review_detects_type_difference(self):
        review = review_adapter_against_catalog(self.adapter, synthetic_catalog())
        self.assertEqual(review['summary']['bindings_metadata_match'], 4)
        self.assertEqual(review['summary']['bindings_proposed'], 4)
        self.assertEqual(review['summary']['bindings_approved'], 0)
        self.assertEqual(review['summary']['relations_columns_found'], 2)
        self.assertEqual(review['summary']['relations_type_review'], 1)
        self.assertEqual(review['summary']['relations_approved'], 0)
        self.assertTrue(review['review_required'])
        self.assertEqual(next(r['metadata_status'] for r in review['relations']
                              if r['id'] == 'decision_application'), 'TYPE_GJENNOMGANG')

    def test_adapter_reports_missing_table_and_key(self):
        catalog = synthetic_catalog()
        review = review_adapter_against_catalog(self.adapter,
                     [t for t in catalog if t['table'] != 'People'])
        self.assertEqual(next(b['metadata_status'] for b in review['bindings']
                              if b['entity_id'] == 'person'), 'TABELL_MANGLER')
        catalog[0]['primary_key'] = ['UNKNOWN_ID']
        review = review_adapter_against_catalog(self.adapter, catalog)
        self.assertEqual(next(b['metadata_status'] for b in review['bindings']
                              if b['entity_id'] == 'person'), 'NOKKEL_KREVER_GJENNOMGANG')

    def test_report_exports_separate_review_csv(self):
        review = review_adapter_against_catalog(self.adapter, synthetic_catalog())
        result = {
            'status': 'DELVIS_KONTROLLERT', 'scan_rows': False,
            'summary': {'tables': 0, 'tables_verified': 0,
                        'metadata_rows_total': 0, 'actual_rows_total': 0,
                        'carriers': 0, 'carriers_verified': 0},
            'catalog': [], 'carriers': [], 'findings': [], 'discovery': {},
            'adapter_review': review,
            'system_category': {'code': '6-18', 'label': 'Sosialtjeneste',
                                'domain_id': 'sosialtjeneste'},
        }
        with patch('siard_workflow.core.content_qa.reporting._pdf_qa'):
            files = write_qa_reports(result, self.root, 'synthetic')
        self.assertTrue(Path(files['adapter_review_bindings_csv']).is_file())
        self.assertTrue(Path(files['adapter_review_relations_csv']).is_file())
        data = json.loads(Path(files['json']).read_text('utf-8'))
        self.assertEqual(data['adapter_review']['summary']['bindings_proposed'], 4)
        self.assertEqual(data['system_category']['code'], '6-18')


if __name__ == '__main__':
    unittest.main()
