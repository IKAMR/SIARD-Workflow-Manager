"""Operation/CLI integration tests against synthetic SIARD archives."""
import json
from pathlib import Path
import tempfile
import unittest

from siard_workflow.core.context import WorkflowContext
from siard_workflow.operations.content_qa_operation import ContentQAOperation
from siard_workflow.core.content_qa.__main__ import main as qa_main
from test_content_qa import example_profile, synthetic_siard


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = synthetic_siard(self.root)
        self.log_dir = self.root / 'logs'

    def test_mapped_quality_report_ok(self):
        profile = self.root / 'mapped.json'
        profile.write_text(json.dumps(example_profile()), encoding='utf-8')
        ctx = WorkflowContext(siard_path=self.archive)
        ctx.metadata['log_dir'] = str(self.log_dir)
        op = ContentQAOperation(profile_file=str(profile), scan_rows=True)
        before = self.archive.read_bytes()
        result = op.run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_status'], 'GODKJENT')
        self.assertEqual(result.data['qa_tables_verified'], 2)
        self.assertEqual(result.data['qa_carriers_verified'], 2)
        self.assertEqual(before, self.archive.read_bytes())
        self.assertTrue(Path(result.data['qa_report_pdf']).is_file())

    def test_unmapped_profile_is_not_green(self):
        ctx = WorkflowContext(siard_path=self.archive)
        ctx.metadata['log_dir'] = str(self.log_dir)
        op = ContentQAOperation()
        result = op.run(ctx)
        self.assertFalse(result.success, result.message)
        self.assertEqual(result.data['qa_status'], 'DELVIS_KONTROLLERT')
        self.assertEqual(result.data['qa_carriers_verified'], 0)
        self.assertTrue(Path(result.data['qa_report_pdf']).is_file())

    def test_missing_archive_produces_failure(self):
        ctx = WorkflowContext(siard_path=self.root / 'missing.siard')
        result = ContentQAOperation().run(ctx)
        self.assertFalse(result.success)

    def _mapped_context(self, *, extracted=None):
        profile = self.root / 'mapped.json'
        profile.write_text(json.dumps(example_profile()), encoding='utf-8')
        ctx = WorkflowContext(siard_path=self.archive, extracted_path=extracted)
        ctx.metadata['log_dir'] = str(self.log_dir)
        return ctx, profile

    def _extracted_sample(self):
        return synthetic_siard(self.root / 'other', zip_it=False)

    def test_default_auto_reads_active_siard(self):
        ctx, profile = self._mapped_context()
        result = ContentQAOperation(profile_file=str(profile)).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_mode'], 'Automatisk')
        self.assertEqual(result.data['qa_source_type'], 'siard_fil')
        self.assertEqual(result.data['qa_source_name'], self.archive.name)
        saved = json.loads(Path(result.data['qa_report_json']).read_text(encoding='utf-8'))
        self.assertEqual(saved['source_type'], 'siard_fil')
        self.assertEqual(saved['input_siard_name'], self.archive.name)

    def test_auto_prefers_workflow_extracted_directory(self):
        folder = self._extracted_sample()
        ctx, profile = self._mapped_context(extracted=folder)
        before_zip = self.archive.read_bytes()
        before_xml = (folder / 'header' / 'metadata.xml').read_bytes()
        result = ContentQAOperation(profile_file=str(profile)).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_type'], 'utpakket_siard')
        self.assertEqual(result.data['qa_source_origin'], 'Arbeidsflytens utpakking')
        self.assertEqual(result.data['qa_tables_verified'], 2)
        self.assertEqual(self.archive.read_bytes(), before_zip)
        self.assertEqual((folder / 'header' / 'metadata.xml').read_bytes(), before_xml)
        self.assertTrue(Path(result.data['qa_report_pdf']).name.startswith(self.archive.stem))
        saved = json.loads(Path(result.data['qa_report_json']).read_text(encoding='utf-8'))
        self.assertEqual(saved['source_type'], 'utpakket_siard')
        self.assertEqual(saved['source_name'], folder.name)
        self.assertEqual(saved['input_siard_name'], self.archive.name)

    def test_direct_unpacked_source_without_archive_file(self):
        folder = self._extracted_sample()
        profile = self.root / 'mapped.json'
        profile.write_text(json.dumps(example_profile()), encoding='utf-8')
        ctx = WorkflowContext(siard_path=folder)
        ctx.metadata['log_dir'] = str(self.log_dir)
        result = ContentQAOperation(profile_file=str(profile)).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_type'], 'utpakket_siard')
        self.assertEqual(result.data['qa_source_origin'], 'Aktiv utpakket SIARD-mappe')

    def test_direct_unpacked_source_rejects_forced_archive(self):
        folder = self._extracted_sample()
        ctx = WorkflowContext(siard_path=folder)
        result = ContentQAOperation(source_mode='SIARD-fil').run(ctx)
        self.assertFalse(result.success)
        self.assertIn('SIARD-fil finnes ikke', result.message)

    def test_packed_and_unpacked_have_same_qa_counts(self):
        folder = self._extracted_sample()
        ctx, profile = self._mapped_context(extracted=folder)
        unpacked = ContentQAOperation(profile_file=str(profile),
                                      source_mode='Utpakket SIARD').run(ctx)
        packed = ContentQAOperation(profile_file=str(profile),
                                    source_mode='SIARD-fil').run(ctx)
        self.assertTrue(unpacked.success, unpacked.message)
        self.assertTrue(packed.success, packed.message)
        for key in ('qa_status', 'qa_tables', 'qa_tables_verified',
                    'qa_pk_verified', 'qa_carriers_verified', 'qa_relations_verified'):
            self.assertEqual(unpacked.data[key], packed.data[key], key)

    def test_source_options_roundtrip_with_saved_params(self):
        original = ContentQAOperation(source_mode='Utpakket SIARD',
                                      unpacked_dir=r'D:\SIARD\ferdig-utpakket',
                                      scan_rows=False)
        saved = json.loads(json.dumps(original.params))
        reopened = ContentQAOperation(**saved)
        self.assertEqual(reopened.params['source_mode'], 'Utpakket SIARD')
        self.assertEqual(reopened.params['unpacked_dir'], r'D:\SIARD\ferdig-utpakket')
        self.assertFalse(reopened.params['scan_rows'])

    def test_explicit_archive_ignores_unpacked_worktree(self):
        folder = self._extracted_sample()
        ctx, profile = self._mapped_context(extracted=folder)
        result = ContentQAOperation(profile_file=str(profile),
                                    source_mode='SIARD-fil').run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_type'], 'siard_fil')
        self.assertEqual(result.data['qa_source_mode'], 'SIARD-fil')
        self.assertEqual(result.data['qa_source_name'], self.archive.name)

    def test_explicit_unpacked_workflow_directory(self):
        folder = self._extracted_sample()
        ctx, profile = self._mapped_context(extracted=folder)
        result = ContentQAOperation(profile_file=str(profile),
                                    source_mode='Utpakket SIARD').run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_type'], 'utpakket_siard')

    def test_explicit_unpacked_missing_worktree_fails(self):
        ctx, profile = self._mapped_context()
        result = ContentQAOperation(profile_file=str(profile),
                                    source_mode='Utpakket SIARD').run(ctx)
        self.assertFalse(result.success)
        self.assertIn('ingen mappe', result.message)

    def test_unpacked_manual_folder_without_workflow_unpack(self):
        folder = self._extracted_sample()
        ctx, profile = self._mapped_context()
        result = ContentQAOperation(profile_file=str(profile),
                                    source_mode='Utpakket SIARD',
                                    unpacked_dir=str(folder)).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_origin'], 'Manuelt valgt mappe')
        self.assertEqual(result.data['qa_source_type'], 'utpakket_siard')

    def test_manual_directory_has_priority_in_auto_mode(self):
        selected = self._extracted_sample()
        wrong_workflow_dir = self.root / 'other_temp'
        wrong_workflow_dir.mkdir()
        ctx, profile = self._mapped_context(extracted=wrong_workflow_dir)
        result = ContentQAOperation(profile_file=str(profile),
                                    unpacked_dir=str(selected)).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_origin'], 'Manuelt valgt mappe')

    def test_explicit_invalid_manual_directory_must_not_fallback(self):
        ctx, profile = self._mapped_context()
        result = ContentQAOperation(profile_file=str(profile),
                                    unpacked_dir=str(self.root / 'notfound')).run(ctx)
        self.assertFalse(result.success)
        self.assertIn('finnes ikke', result.message)

    def test_existing_non_siard_folder_is_not_silent_fallback(self):
        folder = self.root / 'not_siard'
        folder.mkdir()
        ctx, profile = self._mapped_context(extracted=folder)
        result = ContentQAOperation(profile_file=str(profile)).run(ctx)
        self.assertFalse(result.success)
        self.assertIn('metadata.xml', result.message)

    def test_missing_extraction_after_cleanup_auto_falls_back(self):
        ctx, profile = self._mapped_context(extracted=self.root / 'cleaned_worktree')
        result = ContentQAOperation(profile_file=str(profile)).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_source_type'], 'siard_fil')

    def test_invalid_source_mode_fails(self):
        ctx, profile = self._mapped_context()
        result = ContentQAOperation(profile_file=str(profile),
                                    source_mode='typo').run(ctx)
        self.assertFalse(result.success)
        self.assertIn('Ukjent QA-kildevalg', result.message)

    def test_cli_mapped_exit_zero(self):
        profile = self.root / 'mapped.json'
        profile.write_text(json.dumps(example_profile()), encoding='utf-8')
        code = qa_main([str(self.archive), '--profile', str(profile),
                        '--out', str(self.log_dir)])
        self.assertEqual(code, 0)

    def test_cli_default_is_partial(self):
        code = qa_main([str(self.archive), '--out', str(self.log_dir)])
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
