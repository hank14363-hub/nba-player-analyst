"""COVID archive labels accept delayed dates without reclassifying model scope."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError
from season_windows import archive_window,validate_archive_date
from advanced_percentiles import historical_rows
from historical_epm import prepare_import,sha
import test_historical_epm as fixtures


class SeasonWindowTests(unittest.TestCase):
    def test_delayed_finals_dates_allowed_as_archive_only(self):
        for season,stamp in [('2019-20','2020-10-11'),('2020-21','2021-07-20')]:
            with self.subTest(season=season):
                self.assertEqual(validate_archive_date(season,stamp).isoformat(),stamp)

    def test_reviewed_windows_do_not_overlap_neighbors(self):
        seasons=['2018-19','2019-20','2020-21','2021-22','2022-23']
        for previous,current in zip(seasons,seasons[1:]):
            self.assertLess(archive_window(previous)[1],archive_window(current)[0])

    def test_dates_from_prior_delayed_season_are_rejected(self):
        for season,stamp in [('2020-21','2020-10-11'),('2021-22','2021-07-20')]:
            with self.subTest(season=season),self.assertRaises(DataError):validate_archive_date(season,stamp)

    def test_ordinary_season_keeps_original_window(self):
        self.assertEqual(tuple(d.isoformat() for d in archive_window('2017-18')),('2017-07-01','2018-06-30'))
        with self.assertRaises(DataError):validate_archive_date('2017-18','2018-07-01')

    def test_invalid_date_rejected_as_data_error(self):
        for stamp in ('not a date','2020-02-30',None):
            with self.subTest(stamp=stamp),self.assertRaises(DataError):validate_archive_date('2019-20',stamp)

    def test_exception_window_boundaries(self):
        for season in ['2019-20','2020-21','2021-22']:
            for stamp in archive_window(season):self.assertEqual(validate_archive_date(season,stamp.isoformat()),stamp)

    def fixture(self,season,stamp):
        fixture=fixtures.HistoricalEpmTests();fixture.setUp()
        fixture.base['season']=season
        for source in fixture.base['sources'].values():
            if 'season' in source:source['season']=season
        row=fixture.rows[0];row.update(season=str(int(season[:4])+1),game_dt=stamp)
        embedded=json.loads(row['raw']);embedded.update(season=int(season[:4])+1,game_dt=stamp)
        row['raw']=json.dumps(embedded)
        return fixture

    def test_single_import_and_population_share_exception_rules(self):
        for season,stamp in [('2019-20','2020-10-11'),('2020-21','2021-07-20')]:
            with self.subTest(season=season):
                fixture=self.fixture(season,stamp);payload=fixture.payload()
                with patch('historical_epm.CSV_SHA',sha(payload)):
                    bundle,_=prepare_import(fixture.base,fixtures.PID,payload,'2026-10-22T10:00:00+08:00')
                dataset=bundle['impact_data']['datasets'][0]
                self.assertEqual(dataset['estimate_type'],'historical_snapshot_unverified')
                self.assertEqual(dataset['cutoff'],stamp)
                rows=historical_rows(fixture.rows,season,fixture.rows[0]['source'])
                self.assertEqual(rows[0]['as_of'],stamp)

    def test_population_still_rejects_out_of_window_row(self):
        fixture=self.fixture('2020-21','2020-10-11')
        with self.assertRaises(DataError):historical_rows(fixture.rows,'2020-21',fixture.rows[0]['source'])


if __name__=='__main__':unittest.main()
