"""a7 regression: generic QA and separate execution/QA verdicts.

Synthetic SIARD only; no archive records and no external adapter are required.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from siard_workflow.core.context import WorkflowContext
from siard_workflow.operations.content_qa_operation import ContentQAOperation
from test_content_qa_a6 import make_fixture
from siard_workflow.core.content_qa.migration_a6 import unsupported_legacy_options
from siard_workflow.core.content_qa.domain_metrics import build_domain_metrics


class ContentQAA7Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_catalog_reports_distinguish_execution_from_qa(self):
        source = make_fixture(self.root, include_null=False)
        ctx = WorkflowContext(siard_path=source)
        ctx.metadata['log_dir'] = str(self.root / 'logs')
        result = ContentQAOperation(domain_profile='saksarkiv',
                                    source_mode='SIARD-fil',
                                    scan_rows=False).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_execution_status'], 'FULLFORT')
        self.assertEqual(result.data['qa_status'], 'DELVIS_KONTROLLERT')
        data = json.loads(Path(result.data['qa_report_json']).read_text('utf8'))
        self.assertEqual(data['execution_status'], 'KONTROLL_FULLFORT')
        self.assertEqual(data['status'], 'DELVIS_KONTROLLERT')
        self.assertFalse(data['scan_rows'])
        self.assertEqual(data['summary']['actual_rows_total'], 0)
        self.assertTrue(Path(result.data['qa_report_pdf']).is_file())

    def test_legacy_vendor_setting_cannot_write_adapter(self):
        source = make_fixture(self.root, include_null=False)
        private_lib = self.root / 'external'
        private_lib.mkdir()
        ctx = WorkflowContext(siard_path=source)
        ctx.metadata['log_dir'] = str(self.root / 'logs')
        result = ContentQAOperation(domain_profile='saksarkiv',
                                    propose_ephorte_noark4_adapter=True,
                                    resources_root=str(private_lib),
                                    scan_rows=False).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertFalse(list(private_lib.rglob('*.json')))
        self.assertNotIn('qa_adapter_proposal_file', result.data)
        self.assertIsNone(result.data['qa_semantic_metrics_csv'])

    def test_old_vendor_parameter_is_only_migration_notice(self):
        warnings = unsupported_legacy_options({
            'propose_ephorte_noark4_adapter': True})
        self.assertEqual(len(warnings), 1)
        self.assertIn('deaktivert', warnings[0])
        self.assertEqual(unsupported_legacy_options({}), [])

    def test_generic_metrics_require_explicit_standard(self):
        self.assertIsNone(build_domain_metrics({}, {'domain_id':'saksarkiv'}))
        self.assertIsNone(build_domain_metrics({}, {'standard_id':'unknown'}))

    def test_operation_has_no_system_specific_default_option(self):
        self.assertNotIn('propose_ephorte_noark4_adapter',
                         ContentQAOperation.default_params)


if __name__ == '__main__':
    unittest.main()
