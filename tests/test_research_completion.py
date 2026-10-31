"""The final report exposes missing media, commentary and percentile radar work."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from editorial_audit import audit


def sample():
    return dict(data_kind='nba',request=dict(advanced_percentiles=True,percentile_protocol='0.2.0',
        impact_policy='retained_only',comparisons=False),percentile_context=dict(groups=[dict(family='NBA',entries=[dict(status='ok',percentile_metric_id='PCTL_TS_PCT')])]),
        impact_context={},comparison_context={})


class CompletionGateTests(unittest.TestCase):
    def test_missing_radar_is_reported_when_percentiles_are_available(self):
        findings=audit({},sample(),{'claims':[]})['findings']
        self.assertIn('percentile_radar_missing',{f['code'] for f in findings})

    def test_explicit_bars_is_an_intentional_choice(self):
        analysis=sample();content={'percentile_presentation':'bars'}
        findings=audit(content,analysis,{'claims':[]})['findings']
        self.assertNotIn('percentile_radar_missing',{f['code'] for f in findings})

    def test_media_and_commentary_gaps_remain_visible(self):
        findings=audit({},sample(),{'claims':[]})['findings']
        codes={f['code'] for f in findings}
        self.assertIn('commentary_not_attempted',codes)
        # Media absence is checked by media_research.audit; editorial audit still
        # reports the two writing omissions that commonly hide the gap.
        self.assertIn('percentile_radar_missing',codes)


if __name__=='__main__':unittest.main()
