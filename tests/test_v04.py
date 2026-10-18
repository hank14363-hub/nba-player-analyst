import copy
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import read_json, DataError
from calculate_metrics import analyze
from fetch_data import Fetcher, FetchError
from book_visuals import visuals
from team_themes import select_theme
from render_research_book import markdown_body, source_disclosure
from poster_contract import derived_metrics


class Improvements(unittest.TestCase):
    def setUp(self):
        self.b = read_json(ROOT / 'examples/demo_bundle.json')
        self.req = {'player': 'MVP Demo Guard', 'season': '2024-25', 'season_type': 'Regular Season', 'team_id': 0}

    def metric(self, b, mid):
        return next(m for m in analyze(b, self.req)['metrics'] if m['metric_id'] == mid)

    def onoff_bundle(self):
        b = copy.deepcopy(self.b)
        base = b['tables']['player_base'][0]
        tid = base['TEAM_ID']
        team = next(r for r in b['tables']['team_base'] if r['TEAM_ID'] == tid)
        team['MIN'] = base['MIN'] + 1000
        b['tables']['player_onoff'] = [dict(PLAYER_ID=base['PLAYER_ID'], TEAM_ID=tid, COURT_STATUS=state, MIN=mins,
            OFF_RATING=off, DEF_RATING=defense, NET_RATING=off-defense)
            for state, mins, off, defense in [('On', base['MIN'], 115, 112), ('Off', 1000, 110, 111)]]
        b['sources']['P_ONOFF'] = dict(b['sources']['P_BASE'], team_id=tid, sample_scope='full_team_season', metric_definition='team_oncourt')
        return b

    def test_nba_mean_minutes_preserve_assisted_values(self):
        b = self.b; r = b['tables']['player_scoring'][0]
        r['MIN'] = b['tables']['player_base'][0]['MIN'] / r['GP']
        b['sources']['P_SCORE']['endpoint'] = 'leaguedashplayerstats'
        self.assertEqual(self.metric(b, 'PCT_AST_FGM')['status'], 'ok')

    def test_csv_string_fields_keep_valid_scoring_and_chart(self):
        b = self.b; r = b['tables']['player_scoring'][0]
        r['MIN'] = str(b['tables']['player_base'][0]['MIN'] / r['GP'])
        r['GP'] = str(r['GP'])
        b['sources']['P_SCORE']['endpoint'] = 'leaguedashplayerstats'
        b['tables']['player_base'][0] = {k: str(v) if isinstance(v, (int, float)) else v for k, v in b['tables']['player_base'][0].items()}
        a = analyze(b, self.req)
        self.assertEqual(next(m['status'] for m in a['metrics'] if m['metric_id']=='PCT_AST_FGM'), 'ok')
        self.assertTrue(all(m['status']=='ok' for m in derived_metrics(a)))

    def test_foreign_mean_minutes_not_silently_accepted(self):
        r = self.b['tables']['player_scoring'][0]
        r['MIN'] = self.b['tables']['player_base'][0]['MIN'] / r['GP']
        self.assertEqual(self.metric(self.b, 'PCT_AST_FGM')['status'], 'missing')

    def test_nba_wrong_shot_sample_excluded(self):
        self.b['sources']['P_SCORE']['endpoint'] = 'leaguedashplayerstats'
        self.b['tables']['player_scoring'][0]['FGA'] = 1
        self.assertEqual(self.metric(self.b, 'PCT_AST_FGM')['status'], 'missing')

    def test_inconsistent_assisted_pair_is_missing(self):
        self.b['tables']['player_scoring'][0]['PCT_UAST_FGM'] = .99
        self.assertEqual(self.metric(self.b, 'PCT_AST_FGM')['status'], 'missing')

    def test_third_party_individual_rating_not_oncourt(self):
        self.b['data_kind'] = 'nba'
        self.assertEqual(self.metric(self.b, 'ONCOURT_DEF_RATING')['status'], 'missing')

    def test_actual_on_minus_off_not_team_total(self):
        m = self.metric(self.onoff_bundle(), 'ON_OFF_DIFFERENTIAL')
        self.assertEqual(m['value'], 4)
        self.assertEqual(m['source_ids'], ['P_ONOFF'])

    def test_no_off_row_stays_missing(self):
        b = self.onoff_bundle(); b['tables']['player_onoff'].pop()
        self.assertIsNone(self.metric(b, 'ON_OFF_DIFFERENTIAL')['value'])

    def test_duplicate_on_row_stays_missing(self):
        b = self.onoff_bundle(); b['tables']['player_onoff'].append(copy.deepcopy(b['tables']['player_onoff'][0]))
        self.assertIsNone(self.metric(b, 'ON_OFF_DIFFERENTIAL')['value'])

    def test_five_player_minutes_rejected(self):
        b = self.onoff_bundle(); b['tables']['team_base'][0]['MIN'] *= 5
        self.assertIsNone(self.metric(b, 'ON_OFF_DIFFERENTIAL')['value'])

    def test_traded_partial_minutes_rejected(self):
        b = self.onoff_bundle(); b['tables']['player_onoff'][0]['MIN'] -= 100
        self.assertIsNone(self.metric(b, 'ON_OFF_DIFFERENTIAL')['value'])

    def test_net_identity_rejected(self):
        b = self.onoff_bundle(); b['tables']['player_onoff'][0]['NET_RATING'] = 99
        self.assertIsNone(self.metric(b, 'ON_OFF_DIFFERENTIAL')['value'])

    def test_missing_data_never_produces_onoff_svg(self):
        a = analyze(self.b, self.req)
        self.assertIsNone(visuals(a, select_theme(a, 'auto'))['onoff']['svg'])

    def test_allowed_generated_chart_embeds(self):
        self.assertIn('<svg', markdown_body('![已有数据图](charts/test.svg)', {}, {'test.svg': '<svg/>'}))

    def test_caption_with_source_citation_embeds(self):
        rendered = markdown_body('![解释分母。[P_BASE]](charts/test.svg)', {'P_BASE': {}}, {'test.svg': '<svg/>'})
        self.assertIn('<svg', rendered)
        self.assertIn('#source-P_BASE', rendered)

    def test_indexed_source_quality_is_visible(self):
        self.assertIn('原页未直接核验', source_disclosure(['P_100'], {'P_100': {'direct_page_verified': False}}))

    def test_remote_image_is_not_fetched_or_embedded(self):
        self.assertNotIn('<img', markdown_body('![test](https://example.com/test.svg)', {}, {}))

    def test_access_denied_does_not_retry(self):
        class Response: status_code = 403
        class Error(Exception): response = Response()
        calls = []
        def transport(*args): calls.append(1); raise Error()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FetchError) as caught:
                Fetcher(Path(tmp), retries=2, transport=transport, sleep=lambda _: None).table('player_base', '2024-25', 'Regular Season')
            self.assertEqual(caught.exception.category, 'access_denied')
            self.assertEqual(len(calls), 1)

    def test_zero_tracking_attempts_do_not_become_zero_skill(self):
        base = self.b['tables']['player_base'][0]
        self.b['tables']['tracking_catchshoot'] = [dict(base, CATCH_SHOOT_FGA=0, CATCH_SHOOT_FG_PCT=0, CATCH_SHOOT_EFG_PCT=0)]
        self.b['sources']['TR_CATCH'] = dict(self.b['sources']['P_BASE'], per_mode='PerGame')
        self.assertIsNone(self.metric(self.b, 'CATCH_SHOOT_EFG_PCT')['value'])


if __name__ == '__main__': unittest.main()
