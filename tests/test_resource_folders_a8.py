"""Regression: three independent external folders, no proprietary templates in repo."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from siard_workflow.core.content_qa.resource_folders import (
    load_resource_folders, save_resource_folders, validate_resource_folders,
    inspect_resource_folders, ResourceFolderError,
)


class ResourceFoldersA8Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dirs = {}
        for key in ('decom_templates_dir', 'kdrs_sok_vis_dir', 'system_adapter_dir'):
            d = self.root / key
            d.mkdir()
            self.dirs[key] = str(d)
        self.cfg = self.root / 'resource_folders.json'

    def test_three_different_folders_and_decom_original_setting(self):
        prior = {'json_template_dir': self.dirs['decom_templates_dir']}
        with patch('siard_workflow.core.content_qa.resource_folders.get_config',
                   side_effect=lambda key: prior.get(key, '')) as read:
            with patch('siard_workflow.core.content_qa.resource_folders.save_config') as save:
                save_resource_folders(self.dirs, config_file=self.cfg)
                loaded = load_resource_folders(config_file=self.cfg)
        self.assertEqual(loaded, self.dirs)
        # Do not rewrite existing Decom setting or mix it with the two new ones.
        save.assert_not_called()
        self.assertGreaterEqual(read.call_count, 2)
        raw = self.cfg.read_text('utf-8')
        self.assertIn('system_adapter_dir', raw)
        self.assertIn('kdrs_sok_vis_dir', raw)
        self.assertNotIn('decom_templates_dir', raw)

    def test_decom_update_uses_original_config_key(self):
        original = {'json_template_dir': ''}
        def save_config(value):
            original.update(value)
        with patch('siard_workflow.core.content_qa.resource_folders.get_config',
                   side_effect=lambda key: original.get(key, '')):
            with patch('siard_workflow.core.content_qa.resource_folders.save_config',
                       side_effect=save_config) as save:
                save_resource_folders(self.dirs, config_file=self.cfg)
                loaded = load_resource_folders(config_file=self.cfg)
        save.assert_called_once_with({'json_template_dir': self.dirs['decom_templates_dir']})
        self.assertEqual(loaded, self.dirs)

    def test_nonexistent_directory_rejected(self):
        invalid = dict(self.dirs, system_adapter_dir=str(self.root / 'missing'))
        with self.assertRaises(ResourceFolderError):
            validate_resource_folders(invalid)

    def test_empty_values_allowed_and_no_automatic_import(self):
        vals = {'decom_templates_dir': '', 'kdrs_sok_vis_dir': '', 'system_adapter_dir': ''}
        self.assertEqual(validate_resource_folders(vals), vals)
        self.assertFalse(inspect_resource_folders(vals)['configured'])
        self.assertFalse(inspect_resource_folders(self.dirs)['automatic_adapter_approval'])
        self.assertFalse(inspect_resource_folders(self.dirs)['kdrs_templates_used_for_qa'])

    def test_broken_config_not_silently_ignored(self):
        self.cfg.write_text('{not json', encoding='utf-8')
        with self.assertRaises(ResourceFolderError):
            load_resource_folders(config_file=self.cfg)


if __name__ == '__main__':
    unittest.main()
