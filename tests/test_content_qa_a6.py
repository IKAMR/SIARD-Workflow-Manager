"""a6 regression tests: empty SQL strings, explicit NULL and QA verdicts.

All test data is synthetic. No archival data is included in repository tests.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from siard_workflow.core.context import WorkflowContext
from siard_workflow.core.content_qa import run_content_qa
from siard_workflow.core.content_qa.source import SiardSource
from siard_workflow.operations.content_qa_operation import ContentQAOperation
from siard_workflow.core.content_qa.model_catalog import resolve_qa_model

SCHEMA_NS = 'http://www.bar.admin.ch/xmlns/siard/2/metadata.xsd'
TABLE_NS = 'http://www.bar.admin.ch/xmlns/siard/2/table.xsd'
NIL_NS = 'http://www.w3.org/2001/XMLSchema-instance'


def make_fixture(root: Path, include_null: bool) -> Path:
    ET.register_namespace('', SCHEMA_NS)
    md = ET.Element('{' + SCHEMA_NS + '}siardArchive')
    schemas = ET.SubElement(md, '{' + SCHEMA_NS + '}schemas')
    schema = ET.SubElement(schemas, '{' + SCHEMA_NS + '}schema')
    ET.SubElement(schema, '{' + SCHEMA_NS + '}name').text = 'dbo'
    ET.SubElement(schema, '{' + SCHEMA_NS + '}folder').text = 'schema0'
    tables = ET.SubElement(schema, '{' + SCHEMA_NS + '}tables')
    table = ET.SubElement(tables, '{' + SCHEMA_NS + '}table')
    ET.SubElement(table, '{' + SCHEMA_NS + '}name').text = 'LAGRFORMAT'
    ET.SubElement(table, '{' + SCHEMA_NS + '}folder').text = 'table124'
    ET.SubElement(table, '{' + SCHEMA_NS + '}rows').text = '3' if include_null else '2'
    cols = ET.SubElement(table, '{' + SCHEMA_NS + '}columns')
    col = ET.SubElement(cols, '{' + SCHEMA_NS + '}column')
    ET.SubElement(col, '{' + SCHEMA_NS + '}name').text = 'LF_KODE'
    ET.SubElement(col, '{' + SCHEMA_NS + '}type').text = 'VARCHAR(10)'
    ET.SubElement(col, '{' + SCHEMA_NS + '}nullable').text = 'false'
    pk = ET.SubElement(table, '{' + SCHEMA_NS + '}primaryKey')
    ET.SubElement(pk, '{' + SCHEMA_NS + '}column').text = 'LF_KODE'

    ET.register_namespace('', TABLE_NS)
    root_table = ET.Element('{' + TABLE_NS + '}table')
    values = ['PDF', ''] + ([None] if include_null else [])
    for value in values:
        row = ET.SubElement(root_table, '{' + TABLE_NS + '}row')
        cell = ET.SubElement(row, '{' + TABLE_NS + '}c1')
        if value is None:
            cell.set('{' + NIL_NS + '}nil', 'true')
        else:
            cell.text = value
    target = root / 'synthetic_lagrformat.siard'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('header/metadata.xml', ET.tostring(md, encoding='utf-8', xml_declaration=True))
        z.writestr('content/schema0/table124/table124.xml', ET.tostring(root_table, encoding='utf-8', xml_declaration=True))
    return target


def qa_profile() -> dict:
    return {'format_version':1, 'id':'a6_synthetic', 'label':'a6 synthetic',
            'carriers':[{'id':'one', 'label':'one',
                         'source':{'schema':'dbo','table':'LAGRFORMAT'},
                         'key':['LF_KODE']}], 'relations': []}


class ContentQAA6Tests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)

    def test_empty_string_is_not_sql_null(self):
        path = make_fixture(self.root, include_null=True)
        with SiardSource(path) as source:
            table = source.catalog()[0]
            values = [row['LF_KODE'] for _, row in source.rows(table)]
        self.assertEqual(values, ['PDF', '', None])

    def test_pk_empty_is_note_null_is_error(self):
        path = make_fixture(self.root, include_null=True)
        result = run_content_qa(path, qa_profile())
        self.assertEqual(result['status'], 'AVVIK')
        tab = result['catalog'][0]
        self.assertEqual(tab['pk_missing'], 1)
        self.assertEqual(tab['pk_empty'], 1)
        self.assertEqual(tab['pk_duplicates'], 0)
        findings = {x['check_id']:x for x in result['findings']}
        self.assertEqual(findings['metadata_pk_null']['status'], 'AVVIK')
        self.assertEqual(findings['metadata_pk_empty']['status'], 'MERKNAD')

    def test_empty_key_alone_is_not_integrity_failure(self):
        path = make_fixture(self.root, include_null=False)
        result = run_content_qa(path, qa_profile())
        self.assertEqual(result['status'], 'GODKJENT')
        self.assertEqual(result['summary']['pk_empty_values'], 1)
        self.assertEqual(result['summary']['tables_verified'], 1)
        self.assertEqual(result['catalog'][0]['pk_status'], 'OK')
        self.assertEqual(result['catalog'][0]['pk_missing'], 0)
        self.assertEqual(result['catalog'][0]['pk_duplicates'], 0)

    def test_partial_qa_finishes_workflow_without_claiming_approval(self):
        source = make_fixture(self.root, include_null=False)
        ctx = WorkflowContext(siard_path=source)
        ctx.metadata['log_dir'] = str(self.root / 'logs')
        result = ContentQAOperation(domain_profile='saksarkiv', scan_rows=False).run(ctx)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['qa_status'], 'DELVIS_KONTROLLERT')
        self.assertIn('IKKE FAGLIG GODKJENT', result.message)
        report = json.loads(Path(result.data['qa_report_json']).read_text('utf-8'))
        self.assertEqual(report['status'], 'DELVIS_KONTROLLERT')
        self.assertEqual(report['model_context']['mode'], 'domain')

    def test_legacy_selectors_not_exposed_by_model_resolution(self):
        profile, context = resolve_qa_model()
        self.assertEqual(profile['id'], 'domain_saksarkiv')
        self.assertEqual(context['mode'], 'domain')
        with self.assertRaises(TypeError):
            resolve_qa_model(profile_file='obsolete.json')

if __name__ == '__main__':
    unittest.main()
