import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json
from book_contract import validate_content

class ReadingEvidence(unittest.TestCase):
    def setUp(self):
        case=ROOT/'examples/cade-cunningham-2024-25-official-v06'
        self.analysis=read_json(case/'analysis.json')
        self.claims=read_json(case/'claims.json')
        self.content=read_json(case/'book_content.json')
        self.dim=self.content['dimensions'][0]
        self.dim['claim_ids']=['C04']
        self.dim['key_metric_ids']=['TS_PCT']
        self.dim['reading_cards']=[dict(title='效率的含义',claim_ids=['C04'],interpretation='描述投篮与罚球的整体结果。',application='结合任务讨论使用方向。',boundary='尚未控制职责与防守压力。')]
    def errors(self):return validate_content(self.content,self.analysis,self.claims)
    def test_supported_cards_and_legacy_content_are_valid(self):
        self.assertEqual(self.errors(),[])
        del self.dim['reading_cards'];del self.dim['key_metric_ids']
        self.assertEqual(self.errors(),[])
    def test_unregistered_number_rejected_in_interpretation(self):
        self.dim['reading_cards'][0]['interpretation']='效率会提高10%。'
        self.assertTrue(any('quantitative' in e for e in self.errors()))
    def test_card_cannot_borrow_claim_outside_dimension(self):
        self.dim['reading_cards'][0]['claim_ids']=['C12']
        self.assertTrue(any('unknown reference' in e for e in self.errors()))
    def test_metric_and_claim_coverage_remain_auditable(self):
        self.dim['key_metric_ids']=['ONOFF_ON_DEF_RATING']
        self.dim['claim_ids'].append('C05')
        errors=self.errors()
        self.assertTrue(any('key_metric_ids' in e for e in errors))
        self.assertTrue(any('cover all' in e for e in errors))

if __name__=='__main__':unittest.main()
