import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json,DataError
from book_contract import validate_content
from book_shot_explorer import explorer_rows,render_explorer
from book_visuals import visuals
from team_themes import select_theme

class ShotExplorer(unittest.TestCase):
    def setUp(self):
        case=ROOT/'examples/cade-cunningham-2024-25-official-v061'
        self.bundle=read_json(case/'data_bundle.json');self.analysis=read_json(case/'analysis.json')
    def test_complete_event_sample_and_zone_conflict_preserved(self):
        before=copy.deepcopy(self.bundle);rows=explorer_rows(self.bundle,self.analysis)
        self.assertEqual(len(rows),1457);self.assertEqual(sum(r['made'] for r in rows),684)
        conflict=next(r for r in rows if r['zone']=='UNRESOLVED')
        self.assertEqual((conflict['game_id'],conflict['event_id']),('0022400881',637))
        self.assertEqual(conflict['original_type'],'2PT Field Goal');self.assertEqual(self.bundle,before)
    def test_changed_raw_event_is_rejected(self):
        self.bundle['tables']['player_shots'][0]['LOC_X']+=1
        with self.assertRaises(DataError):explorer_rows(self.bundle,self.analysis)
    def test_missing_evidence_does_not_create_an_explorer(self):
        self.analysis.pop('shot_context');self.assertEqual(explorer_rows(self.bundle,self.analysis),[])
    def test_svg_correspondence_and_escaped_metadata(self):
        rows=explorer_rows(self.bundle,self.analysis)
        svg=visuals(self.analysis,select_theme(self.analysis))['shot_locations']['svg']
        html=render_explorer(rows,svg);self.assertEqual(html.count('class="shot-event"'),1457)
        with self.assertRaises(DataError):render_explorer(rows,'<svg></svg>')
        rows[0]['original_zone']='"><script>bad</script>'
        html=render_explorer(rows,svg);self.assertNotIn('<script>bad</script>',html)

class CommentaryContract(unittest.TestCase):
    def setUp(self):
        case=ROOT/'examples/cade-cunningham-2024-25-official-v061'
        self.a=read_json(case/'analysis.json');self.claims=read_json(case/'claims.json');self.b=read_json(case/'book_content.json')
        self.a['sources']['EXT_REVIEW']=dict(source_type='commentary_article',status='ok',direct_page_verified=True,author='Fixture Author',published_at='2025-03-01T00:00:00Z',title='Synthetic review fixture')
        self.claims['claims'].append(dict(id='C_FIXTURE',source_ids=['EXT_REVIEW']))
        self.b['commentary_cards']=[dict(title='外部视角',source_id='EXT_REVIEW',claim_ids=['C_FIXTURE'],view='这是作者观点。',response='保留原始样本。',question='回到具体任务验证。')]
    def test_verified_attributed_source_is_required(self):
        self.assertEqual(validate_content(self.b,self.a,self.claims),[])
        self.a['sources']['EXT_REVIEW']['direct_page_verified']=False
        self.assertTrue(validate_content(self.b,self.a,self.claims))
    def test_article_cannot_borrow_unrelated_claim_or_add_numbers(self):
        self.b['commentary_cards'][0]['claim_ids']=['C04'];self.b['commentary_cards'][0]['view']='效率增长10%。'
        errors=validate_content(self.b,self.a,self.claims)
        self.assertTrue(any('attributed claim' in e for e in errors));self.assertTrue(any('quantitative' in e for e in errors))

if __name__=='__main__':unittest.main()
