"""Migration rejects collisions and invalid evidence before writing output."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError
from upgrade_radar import upgrade


class RadarUpgrade(unittest.TestCase):
    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);s=root/'source';s.mkdir();out=root/'output';out.mkdir()
            note=out/'note';note.write_text('user data')
            with self.assertRaises(DataError):upgrade(s,out)
            self.assertEqual(note.read_text(),'user data')

    def test_source_and_output_must_not_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'case';source.mkdir()
            for out in (source,source/'nested',source.parent):
                with self.assertRaises(DataError):upgrade(source,out)

    def test_invalid_evidence_creates_no_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);s=root/'source';s.mkdir();out=root/'output'
            with patch('upgrade_radar.load_context',side_effect=DataError('raw hash mismatch')):
                with self.assertRaises(DataError):upgrade(s,out)
            self.assertFalse(out.exists())

    def test_changed_existing_metric_is_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);s=root/'source';s.mkdir();out=root/'output'
            old=dict(request=dict(advanced_percentiles=True),metrics=[dict(metric_id='X',value=1)])
            with patch('upgrade_radar.load_context',return_value=(old,None,None,None)),patch('upgrade_radar.read_json',return_value={}),patch('upgrade_radar.verify_retained'),patch('upgrade_radar.analyze',return_value=dict(metrics=[dict(metric_id='X',value=2)])):
                with self.assertRaises(DataError):upgrade(s,out)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
