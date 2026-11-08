"""a5 ePhorte/Noark 4 tests: completely synthetic source data, no vendor SQL."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from siard_workflow.core.content_qa import run_content_qa
from siard_workflow.core.content_qa.model_catalog import (
    ModelError, load_adapter, load_domain_model, resolve_qa_model,
)
from siard_workflow.core.content_qa.ephorte_noark4 import (
    propose_ephorte_adapter, write_private_proposal,
)
from siard_workflow.core.content_qa.semantic_results import build_noark4_metrics
from siard_workflow.core.content_qa.profile import ProfileError, validate_profile
from siard_workflow.core.content_qa.reporting import write_qa_reports
from test_content_qa import SCHEMA_NS, TABLE_NS


def fake_catalog():
    names = [
        ('ARKIV', ['ARCHIVE_ID']), ('ARKIVDEL', ['ARCHIVE_PART_ID']),
        ('NOARKSAK', ['CASE_ID']), ('JOURNPOST', ['POST_ID']),
        ('DOKLINK', ['POST_REF', 'LINK_POS', 'DOCUMENT_REF']),
        ('DOKBESKRIV', ['DOCUMENT_ID']),
        ('DOKVERSJON', ['DOCUMENT_REF', 'VERSION_NO', 'VARIANT_CODE']),
        ('AVSMOT', ['ACTOR_ID']), ('SAKSPART', ['CASE_REF', 'PARTY_NAME']),
        ('ORDNPRINS', ['SCHENOTE_ID']), ('ORDNVERDI', ['SCHEME_REF','CLASS_CODE']),
        ('KLASSERING', ['CASE_REF', 'SCHEME_REF', 'CLASS_CODE']),
        ('MERKNAD', ['NOTE_ID']),
    ]
    return [dict(schema='dbo', table=n, primary_key=pk, columns=[dict(name=k) for k in pk])
            for n,pk in names]


def fk(child, child_fields, parent, parent_fields):
    return dict(child_schema='dbo', child_table=child, child_columns=child_fields,
                parent_schema='dbo', parent_table=parent, parent_columns=parent_fields,
                status='METADATA_LOEST')


def fake_report():
    return dict(source_name='example.siard', catalog=fake_catalog(),
                discovery={'declared_relations': [
                    fk('ARKIVDEL', ['ARCHIVE_REF'], 'ARKIV', ['ARCHIVE_ID']),
                    fk('NOARKSAK', ['ARCHIVE_PART_REF'], 'ARKIVDEL', ['ARCHIVE_PART_ID']),
                    fk('JOURNPOST', ['CASE_REF'], 'NOARKSAK', ['CASE_ID']),
                    fk('DOKLINK', ['POST_REF'], 'JOURNPOST', ['POST_ID']),
                    fk('DOKLINK', ['DOCUMENT_REF'], 'DOKBESKRIV', ['DOCUMENT_ID']),
                    fk('DOKVERSJON', ['DOCUMENT_REF'], 'DOKBESKRIV', ['DOCUMENT_ID']),
                    fk('AVSMOT', ['POST_REF'], 'JOURNPOST', ['POST_ID']),
                    fk('SAKSPART', ['CASE_REF'], 'NOARKSAK', ['CASE_ID']),
                    fk('KLASSERING', ['CASE_REF'], 'NOARKSAK', ['CASE_ID']),
                    fk('KLASSERING', ['SCHEME_REF','CLASS_CODE'], 'ORDNVERDI', ['SCHEME_REF','CLASS_CODE']),
                    fk('ORDNVERDI', ['SCHEME_REF'], 'ORDNPRINS', ['SCHENOTE_ID']),
                ]})


def document_representation_fixture(root: Path, *, null_version=False) -> Path:
    ET.register_namespace('', SCHEMA_NS)
    md = ET.Element('{%s}siardArchive' % SCHEMA_NS)
    schemas = ET.SubElement(md,'{%s}schemas' % SCHEMA_NS)
    schema = ET.SubElement(schemas,'{%s}schema' % SCHEMA_NS)
    ET.SubElement(schema,'{%s}name' % SCHEMA_NS).text='dbo'
    ET.SubElement(schema,'{%s}folder' % SCHEMA_NS).text='schema0'
    tables = ET.SubElement(schema,'{%s}tables' % SCHEMA_NS)
    tab = ET.SubElement(tables,'{%s}table' % SCHEMA_NS)
    ET.SubElement(tab,'{%s}name' % SCHEMA_NS).text='DOKVERSJON'
    ET.SubElement(tab,'{%s}folder' % SCHEMA_NS).text='table0'
    ET.SubElement(tab,'{%s}rows' % SCHEMA_NS).text='4'
    cols=['DOCUMENT_REF','VERSION_NO','VARIANT_CODE']
    colroot=ET.SubElement(tab,'{%s}columns' % SCHEMA_NS)
    for name in cols:
        col=ET.SubElement(colroot,'{%s}column' % SCHEMA_NS)
        ET.SubElement(col,'{%s}name' % SCHEMA_NS).text=name
        ET.SubElement(col,'{%s}type' % SCHEMA_NS).text='VARCHAR(50)'
    pk=ET.SubElement(tab,'{%s}primaryKey' % SCHEMA_NS)
    for name in cols: ET.SubElement(pk,'{%s}column' % SCHEMA_NS).text=name
    ET.register_namespace('', TABLE_NS)
    data=ET.Element('{%s}table' % TABLE_NS)
    rows=[['D1','1','arkiv'],['D1','1','prod'],['D1','2','prod'],['D2','1','prod']]
    if null_version:rows[2][1]=None
    for tup in rows:
        row=ET.SubElement(data,'{%s}row' % TABLE_NS)
        for i,value in enumerate(tup,1):
            child=ET.SubElement(row,'{%s}c%d' % (TABLE_NS,i))
            if value is None:
                # Explicit SQL NULL; an empty element means an empty string.
                child.set('{http://www.w3.org/2001/XMLSchema-instance}nil', 'true')
            else:
                child.text=value
    target=root/'synthetic.siard'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('header/metadata.xml',ET.tostring(md,encoding='utf-8',xml_declaration=True))
        z.writestr('content/schema0/table0/table0.xml',ET.tostring(data,encoding='utf-8',xml_declaration=True))
    return target


class EphorteA5Tests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.tmp=Path(self.td.name)

    def test_domain_is_extended_without_noark5_hardcoding(self):
        model=load_domain_model('saksarkiv')
        self.assertIn('archive_structure',model['domain']['modules'])
        ids={e['id'] for m in model['modules'] for e in m['entities']}
        self.assertIn('archive',ids)
        self.assertIn('archive_part',ids)
        self.assertIn('document_link',ids)
        self.assertIn('document_representation',ids)

    def test_proposals_are_unapproved_and_valid_for_runtime(self):
        adapter,review=propose_ephorte_adapter(fake_report())
        self.assertEqual(adapter['standard_id'],'noark4')
        self.assertGreaterEqual(len(adapter['bindings']),12)
        self.assertGreaterEqual(len(adapter['relations']),9)
        self.assertFalse(review['mapping_is_approved'])
        self.assertTrue(all(x['review_status']=='proposed' for x in adapter['bindings']+adapter['relations']))
        by={b['entity_id']:b for b in adapter['bindings']}
        self.assertEqual(by['case_file']['source']['table'],'NOARKSAK')
        self.assertEqual(by['journal_post']['key'],['POST_ID'])
        self.assertEqual(by['document_representation']['distinct_metrics'],
                         [{'id':'document_versions','columns':['DOCUMENT_REF','VERSION_NO']}])
        src=self.tmp/'private_adapters'
        output=write_private_proposal(fake_report(),src)
        self.assertTrue(Path(output['adapter']).is_file())
        loaded,_=load_adapter(output['adapter'])
        self.assertEqual(loaded,adapter)
        qa_profile,context=resolve_qa_model(adapter_file=output['adapter'])
        self.assertEqual(context['standard_id'],'noark4')
        self.assertEqual(context['bindings_applied'],0)
        self.assertEqual(len(qa_profile['relations']),0)
        self.assertFalse(any(x.get('source') for x in qa_profile['carriers']))
        self.assertGreaterEqual(context['bindings_pending'],len(adapter['bindings']))

    def test_ambiguous_foreign_keys_are_not_guessed(self):
        report=fake_report()
        report['discovery']['declared_relations'].append(
            fk('ORDNVERDI',['OTHER_SCHEME_REF'],'ORDNPRINS',['SCHENOTE_ID']))
        adapter,review=propose_ephorte_adapter(report)
        self.assertFalse(any(r['id']=='classification_value_scheme'
                             for r in adapter['relations']))
        item=next(x for x in review['review'] if x['id']=='classification_value_scheme')
        self.assertEqual(item['status'],'FLERTYDIG')

    def test_collision_never_overwrites_previous_review(self):
        output=self.tmp/'out'
        first=write_private_proposal(fake_report(),output)
        Path(first['adapter']).write_text('{"mine": true}',encoding='utf8')
        with self.assertRaises(ModelError):
            write_private_proposal(fake_report(),output)
        self.assertEqual(Path(first['adapter']).read_text('utf8'),'{"mine": true}')

    def test_invalid_catalog_is_rejected(self):
        with self.assertRaises(ModelError):propose_ephorte_adapter({'catalog':'bad'})
        with self.assertRaises(ModelError):propose_ephorte_adapter({'catalog':[{'schema':1}]})

    def test_approved_representation_counts_distinct_versions_separately(self):
        src=document_representation_fixture(self.tmp)
        adapter,_=propose_ephorte_adapter({'catalog':[dict(
            schema='dbo',table='DOKVERSJON',primary_key=[
              'DOCUMENT_REF','VERSION_NO','VARIANT_CODE'],
            columns=[{'name':x} for x in ['DOCUMENT_REF','VERSION_NO','VARIANT_CODE']])],
            'discovery':{'declared_relations':[]}})
        for b in adapter['bindings']:
            b['review_status']='approved'
        private=self.tmp/'checked.json'
        private.write_text(json.dumps(adapter),encoding='utf8')
        profile,context=resolve_qa_model(adapter_file=str(private))
        report=run_content_qa(src,profile)
        c=next(x for x in report['carriers'] if x['id']=='document_representation')
        self.assertEqual(c['rows'],4)
        self.assertEqual(c['unique'],4)
        self.assertEqual(c['distinct_counts'],{'document_versions':3})
        sem=build_noark4_metrics(report,context)
        rep=next(x for x in sem['metrics'] if x['metric_id']=='document_representation.count')
        ver=next(x for x in sem['metrics'] if x['metric_id']=='document_version.count')
        self.assertEqual(rep['value'],4)
        self.assertEqual(ver['value'],3)
        self.assertFalse(rep['legacy_sql_execution'])
        self.assertEqual(sem['all_requirements_validated'],False)
        self.assertEqual(next(x for x in sem['metrics'] if x['metric_id']=='case_file.count')['value'],None)
        report['semantic_results']=sem
        files=write_qa_reports(report,self.tmp/'reports','synthetic')
        self.assertIn('document_version.count',Path(files['semantic_metrics_csv']).read_text('utf-8-sig'))
        self.assertTrue(Path(files['pdf']).is_file())

    def test_no_scan_never_measures_business_concepts(self):
        src=document_representation_fixture(self.tmp)
        p,context=resolve_qa_model(domain='saksarkiv')
        report=run_content_qa(src,p,scan_rows=False)
        sem=build_noark4_metrics(report,{**context,'standard_id':'noark4'})
        self.assertTrue(all(x['state']=='not_measured' and x['value'] is None
                            for x in sem['metrics']))

    def test_unknown_and_duplicate_projection_rejected(self):
        profile={'format_version':1,'id':'x','label':'X','carriers':[{
            'id':'x','label':'X','source':{'schema':'s','table':'t'},'key':['pk'],
            'distinct_metrics':[{'id':'versions','columns':['a','a']}]}],'relations':[]}
        with self.assertRaises(ProfileError):validate_profile(profile)
        profile['carriers'][0]['distinct_metrics']=[{'id':'versions','columns':['a']},
                                                    {'id':'versions','columns':['a']}]
        with self.assertRaises(ProfileError):validate_profile(profile)
        profile['carriers'][0]['distinct_metrics']=[{'id':'versions','columns':['a'],'sql':'DROP'}]
        with self.assertRaises(ProfileError):validate_profile(profile)

    def test_null_distinct_projection_is_explicitly_excluded(self):
        path=document_representation_fixture(self.tmp,null_version=True)
        p,_=resolve_qa_model(domain='saksarkiv')
        c=next(x for x in p['carriers'] if x['id']=='document_representation')
        c.update(source={'schema':'dbo','table':'DOKVERSJON'},
                 key=['DOCUMENT_REF','VERSION_NO','VARIANT_CODE'],
                 distinct_metrics=[{'id':'document_versions','columns':['DOCUMENT_REF','VERSION_NO']}])
        report=run_content_qa(path,p)
        c2=next(x for x in report['carriers'] if x['id']=='document_representation')
        self.assertEqual(c2['distinct_counts'],{'document_versions':2})
        self.assertEqual(c2['distinct_missing'],{'document_versions':1})
        self.assertEqual(report['status'],'AVVIK')  # Metadata PK has NULL.

    def test_private_proposal_rejects_in_repo_output(self):
        from siard_workflow.core.content_qa.ephorte_noark4 import REPO_ROOT
        with self.assertRaises(ModelError):
            write_private_proposal(fake_report(),REPO_ROOT/'adapters'/'ephorte')

    def test_missing_projection_column_does_not_generate_fake_count(self):
        p,ctx=resolve_qa_model(domain='saksarkiv')
        c=next(x for x in p['carriers'] if x['id']=='document_representation')
        c.update(source={'schema':'dbo','table':'DOKVERSJON'},key=['DOCUMENT_REF','VERSION_NO','VARIANT_CODE'],
                 distinct_metrics=[{'id':'document_versions','columns':['DOES_NOT_EXIST']}])
        report=run_content_qa(document_representation_fixture(self.tmp),p)
        c2=next(x for x in report['carriers'] if x['id']=='document_representation')
        self.assertEqual(c2['status'],'IKKE_KONTROLLERT')
        self.assertEqual(c2['distinct_counts'],{})

    def test_operation_can_write_private_proposal_without_auto_approval(self):
        from siard_workflow.core.context import WorkflowContext
        from siard_workflow.operations.content_qa_operation import ContentQAOperation
        src=document_representation_fixture(self.tmp)
        resources=self.tmp/'external_library'
        resources.mkdir()
        ctx=WorkflowContext(siard_path=src)
        ctx.metadata['log_dir']=str(self.tmp/'operation_logs')
        op=ContentQAOperation(domain_profile='saksarkiv', resources_root=str(resources),
                              propose_ephorte_noark4_adapter=True,scan_rows=False)
        operation_result=op.run(ctx)
        self.assertTrue(operation_result.success)  # Execution finished; no QA approval.
        self.assertEqual(operation_result.data['qa_status'],'DELVIS_KONTROLLERT')
        proposal=Path(operation_result.data['qa_adapter_proposal_file'])
        self.assertTrue(proposal.is_file())
        # Windows TEMP can be reached through junctions/aliases. The writer
        # deliberately returns a canonical path for security; compare both
        # paths canonically rather than checking their textual spelling.
        self.assertTrue(
            proposal.resolve().is_relative_to(resources.resolve()),
            f'Adapterforslaget ble lagret utenfor fagressursmappen: '
            f'{proposal.resolve()} (forventet under {resources.resolve()})',
        )
        self.assertFalse(any(b['review_status']=='approved' for b in load_adapter(proposal)[0]['bindings']))
        self.assertIsNone(operation_result.data['qa_semantic_metrics_csv'])

    def test_operation_rejects_proposal_without_resource_library(self):
        from siard_workflow.core.context import WorkflowContext
        from siard_workflow.operations.content_qa_operation import ContentQAOperation
        source=document_representation_fixture(self.tmp)
        out=ContentQAOperation(domain_profile='saksarkiv',
                               propose_ephorte_noark4_adapter=True,
                               scan_rows=False).run(WorkflowContext(siard_path=source))
        self.assertFalse(out.success)
        self.assertIn('fagressursmappe',out.message)

    def test_standalone_only_when_noark4_is_selected(self):
        self.assertIsNone(build_noark4_metrics({'carriers':[]},{'domain_id':'barnevern','standard_id':'noark4'}))
        self.assertIsNone(build_noark4_metrics({'carriers':[]},{'domain_id':'saksarkiv','standard_id':None}))

if __name__ == '__main__':unittest.main()
