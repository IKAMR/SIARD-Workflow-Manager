"""a7 checkpoint safety regression tests, no external SIARD input."""
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import dataclass

from siard_workflow.core.project_file import ProjectFile

@dataclass
class Operation:
    operation_id: str = 'content_qa'
    label: str = 'Innholdskontroll'
    params: dict = None


class ProjectFileA7Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'sample.siard'

    def test_changed_settings_invalidate_completed_step(self):
        pf = ProjectFile.from_ops(self.source, [Operation(params={'scan_rows': True})])
        pf.mark_completed('content_qa')
        self.assertTrue(pf.is_completed('content_qa'))
        pf.operations[0].params = {'scan_rows': False}  # GUI checkpoint sync
        self.assertFalse(pf.is_completed('content_qa'))
        self.assertEqual(pf.get_status('content_qa'), 'pending')
        self.assertEqual(pf.completed_count, 0)
        self.assertFalse(pf.is_fully_completed)
        pf.mark_completed('content_qa')
        self.assertTrue(pf.is_completed('content_qa'))

    def test_save_as_starts_fresh_project_and_keeps_original(self):
        pf = ProjectFile.from_ops(self.source, [Operation(params={'scan_rows': True})])
        pf.mark_completed('content_qa', ctx_data={'qa_status':'DELVIS_KONTROLLERT'})
        original = self.root / 'run1.siardwf'
        pf.save(original)
        before = original.read_bytes()
        clone = self.root / 'run2.siardwf'
        pf.save(clone)
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(pf.get_status('content_qa'), 'pending')
        self.assertEqual(json.loads(clone.read_text())['operations'][0]['status'], 'pending')
        self.assertEqual(pf.operations[0].ctx_data, {})
        self.assertEqual(pf.operations[0].params, {'scan_rows': True})

    def test_loading_legacy_a6_project_and_editing_settings(self):
        legacy = self.root / 'a6.siardwf'
        data = {
            'version': 1, 'source_siard': str(self.source),
            'created': '2026-11-08T12:00:00', 'updated': '2026-11-08T12:01:00',
            'operations': [{
                'operation_id':'content_qa','label':'Innholdskontroll',
                'params':{'scan_rows':True}, 'status':'completed',
                'output_siard':None,'completed_at':'2026-11-08T12:01:00',
                'error_msg':None,'ctx_data':{'qa_status':'DELVIS_KONTROLLERT'}
            }]
        }
        legacy.write_text(json.dumps(data),encoding='utf8')
        pf = ProjectFile.load(legacy)
        self.assertTrue(pf.is_completed('content_qa'))
        pf.operations[0].params['scan_rows'] = False
        self.assertFalse(pf.is_completed('content_qa'))
        pf.save(legacy)
        self.assertFalse(ProjectFile.load(legacy).is_completed('content_qa'))

    def test_completed_snapshot_cannot_be_modified_implicitly(self):
        pf = ProjectFile.from_ops(self.source, [Operation(params={'one':[1,2]})])
        pf.mark_completed('content_qa')
        pf.operations[0].params['one'].append(3)
        self.assertFalse(pf.is_completed('content_qa'))

if __name__=='__main__':
    unittest.main()
