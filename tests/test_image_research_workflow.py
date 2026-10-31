"""Offline fixtures: plans never claim searches, image-use audits retain real gaps."""
import base64
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import DataError, read_json, write_json
from plan_image_research import build_plan, record_template, write_plan
from media_research import audit, original_key

STAMP = '2026-10-20T10:00:00+08:00'


def analysis():
    return dict(player=dict(id=201939, name='Stephen Curry', reported_team_id=999),
                sample=dict(season='2015-16', season_type='Regular Season'), data_kind='nba',
                request=dict(media_research_audit=True, media_research_protocol='0.2.0'), sources={})


class ImagePlanTests(unittest.TestCase):
    def setUp(self):
        self.a = analysis()

    def test_cross_calendar_years(self):
        p = build_plan(self.a)
        self.assertEqual(p['calendar_years'], ['2015', '2016'])
        self.assertTrue(any('2015 regular season' in q['query'] for q in p['suggested_queries']))
        self.assertTrue(any('2016 regular season' in q['query'] for q in p['suggested_queries']))

    def test_current_reported_team_is_never_inferred(self):
        p = build_plan(self.a)
        self.assertIsNone(p['verified_team_hint'])
        self.assertNotIn('999', str(p['suggested_queries']))

    def test_verified_historical_team_and_alias(self):
        p = build_plan(self.a, team='Golden State Warriors', aliases=['斯蒂芬·库里', 'Steph Curry'])
        self.assertEqual(p['verified_team_hint'], 'Golden State Warriors')
        self.assertTrue(any('斯蒂芬·库里' in q['query'] for q in p['suggested_queries']))

    def test_playoffs_does_not_plan_regular_season(self):
        self.a['sample']['season_type'] = 'Playoffs'
        queries = [q['query'] for q in build_plan(self.a)['suggested_queries'] if q['route'] == 'discovery']
        self.assertTrue(all('playoffs' in query and 'regular season' not in query for query in queries))

    def test_subset_does_not_force_four_images(self):
        p = build_plan(self.a, slots=('cover',))
        self.assertEqual([n['slot'] for n in p['needs']], ['cover'])
        self.assertFalse(any(q['route'] == 'animation_optional' for q in p['suggested_queries']))

    def test_animation_only_a_suggestion(self):
        p = build_plan(self.a, include_animation=True)
        self.assertTrue(any(q['route'] == 'animation_optional' for q in p['suggested_queries']))
        self.assertTrue(all(q['status'] == 'not_executed' for q in p['suggested_queries']))

    def test_plan_does_not_create_execution_claims(self):
        p = build_plan(self.a)
        record = record_template(p)
        self.assertEqual((p['status'], record['status']), ('not_executed', 'pending'))
        self.assertEqual(record['queries'], [])
        self.assertEqual(record['candidates'], [])

    def test_invalid_or_repeated_slots_rejected(self):
        for slots in ((), ('arena',), ('cover', 'cover')):
            with self.subTest(slots=slots), self.assertRaises(DataError):
                build_plan(self.a, slots=slots)

    def test_invalid_season_not_silently_turned_into_dates(self):
        self.a['sample']['season'] = '2015-17'
        with self.assertRaises(DataError):
            build_plan(self.a)

    def test_regeneration_never_changes_actual_log_or_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / 'media_research.json', {'reason': 'real existing user work'})
            (root / 'media').mkdir()
            (root / 'media/photo.jpg').write_bytes(b'unchanged')
            before = (root / 'media_research.json').read_bytes()
            write_plan(root, self.a)
            with self.assertRaises(DataError):
                write_plan(root, self.a)
            write_plan(root, self.a, force=True, slots=('cover',))
            self.assertEqual((root / 'media_research.json').read_bytes(), before)
            self.assertEqual((root / 'media/photo.jpg').read_bytes(), b'unchanged')
            self.assertEqual(read_json(root / 'media_search_plan.json')['status'], 'not_executed')


class ImageAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = analysis()
        # A one-pixel test raster has no NBA identity and is never a real photographic case.
        raster = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a9sAAAAASUVORK5CYII=')
        (self.root / 'media').mkdir()
        (self.root / 'media/fixture.png').write_bytes(raster)
        self.source = dict(provider='OFFLINE TEST FIXTURE, not a live source',
                           url='https://example.org/fixture', retrieved_at=STAMP, status='ok',
                           source_type='illustrative_media', credit='Test fixture', license='TEST ONLY',
                           license_url='https://example.org/test-license', media_date='2016-01-01', changes='none')
        self.a['sources']['EXT_MEDIA_FIXTURE'] = self.source
        self.item = dict(id='fixture', slot='cover', kind='photo', path='media/fixture.png',
                         sha256=hashlib.sha256(raster).hexdigest(), title='Test raster',
                         alt='One-pixel test fixture, no actual player', caption='Offline fixture only',
                         source_ids=['EXT_MEDIA_FIXTURE'])
        self.media = dict(schema_version='0.1.0', identity=record_template(build_plan(self.a))['identity'], items=[self.item])
        self.candidate = dict(page_url=self.source['url'], accessed_at=STAMP, decision='adopted',
                              reason='Offline test, not evidence of source availability',
                              source_id='EXT_MEDIA_FIXTURE', media_id='fixture',
                              verification=dict(identity='verified', rights='verified', visual='verified',
                                                date='capture_verified', season_relation='in_scope', event_type='regular_season'))
        self.record = dict(schema_version='0.2.0', identity=self.media['identity'], status='complete',
                           reason='Single-image fixture scheme only', queries=[], candidates=[self.candidate],
                           needs=[dict(slot='cover', status='covered', reason='Requested only one cover', media_ids=['fixture'])])

    def codes(self):
        write_json(self.root / 'media_research.json', self.record)
        write_json(self.root / 'media_content.json', self.media)
        return [f['code'] for f in audit(self.root, self.a)['findings']]

    def test_complete_single_image_no_universal_image_quota(self):
        self.assertEqual(self.codes(), [])

    def test_plan_template_cannot_pass_as_execution(self):
        self.record = record_template(build_plan(self.a))
        codes = self.codes()
        self.assertIn('media_record_invalid', codes)
        self.assertIn('media_need_invalid', codes)

    def test_new_run_cannot_downgrade_log_to_skip_review(self):
        self.record.pop('schema_version')
        self.assertIn('media_protocol_missing', self.codes())

    def test_missing_needs_detected(self):
        self.record.pop('needs')
        self.assertIn('media_needs_missing', self.codes())

    def test_covered_needs_real_same_slot_asset(self):
        self.record['needs'][0]['slot'] = 'defense'
        self.assertIn('media_need_unlinked', self.codes())

    def test_unavailable_is_a_visible_gap(self):
        self.record['needs'].append(dict(slot='defense', status='unavailable', reason='No suitable licensed original', media_ids=[]))
        self.assertIn('media_complete_with_gap', self.codes())
        self.record.update(status='limited', stop_reason='Cover adopted; defense asset unavailable after actual research')
        self.assertEqual(self.codes(), [])

    def test_optional_not_needed_does_not_force_search(self):
        self.record['needs'].append(dict(slot='defense', status='not_needed', reason='No defense photo requested', media_ids=[]))
        self.assertEqual(self.codes(), [])

    def test_limited_needs_actual_stop_reason(self):
        self.record['status'] = 'limited'
        self.assertIn('media_limited_stop_unexplained', self.codes())

    def test_missing_manual_visual_verification_detected(self):
        self.candidate['verification'].pop('visual')
        self.assertIn('media_verification_incomplete', self.codes())

    def test_unknown_rights_cannot_be_adopted(self):
        self.candidate['verification']['rights'] = 'unknown'
        self.assertIn('media_verification_incomplete', self.codes())

    def test_upload_date_does_not_establish_season_photo(self):
        self.candidate['verification']['date'] = 'upload_only'
        self.assertIn('media_season_unverified', self.codes())

    def test_all_star_cannot_be_regular_season_evidence(self):
        self.candidate['verification']['event_type'] = 'all_star'
        self.assertIn('media_season_unverified', self.codes())

    def test_historical_photo_needs_visible_caption_not_just_alt(self):
        self.candidate['verification']['season_relation'] = 'historical'
        self.candidate['disclosure'] = '2012资料照，仅作人物展示'
        self.item['alt'] = self.candidate['disclosure']
        self.assertIn('media_visible_disclosure_missing', self.codes())
        self.item['caption'] += '；' + self.candidate['disclosure']
        self.assertEqual(self.codes(), [])

    def test_environment_cannot_fill_cover(self):
        self.candidate['verification']['identity'] = 'environment_only'
        self.assertIn('media_environment_as_cover', self.codes())

    def test_unregistered_actual_photo_detected(self):
        self.record['candidates'] = []
        self.assertIn('media_asset_without_adoption', self.codes())

    def test_duplicate_raster_does_not_expand_coverage(self):
        second = dict(self.item, id='duplicate', slot='scoring')
        self.media['items'].append(second)
        self.record['candidates'].append(dict(self.candidate, media_id='duplicate'))
        self.record['needs'].append(dict(slot='scoring', status='covered', reason='Same image should fail', media_ids=['duplicate']))
        self.assertIn('media_duplicate_asset', self.codes())

    def test_flickr_size_retry_not_independent_fallback(self):
        self.media['items'] = []
        self.record.update(status='limited', stop_reason='Only one actual origin',
                           needs=[dict(slot='cover', status='unavailable', reason='Origin denied access', media_ids=[])],
                           candidates=[dict(page_url=url, accessed_at=STAMP, decision='blocked', reason='Fixture HTTP403') for url in
                                       ['https://www.flickr.com/photos/fixture/12345/',
                                        'https://www.flickr.com/photos/fixture/12345/sizes/l/']])
        self.assertIn('media_fallback_not_attempted', self.codes())

    def test_no_search_tools_does_not_require_fake_candidates(self):
        self.media['items'] = []
        self.record.update(status='limited', stop_reason='Runtime has no retrieval tools', candidates=[],
                           limitation='search_and_browse_unavailable', needs=[dict(slot='cover', status='unavailable', reason='No tools', media_ids=[])])
        self.assertEqual(self.codes(), [])

    def test_offline_can_skip_new_protocol(self):
        self.record.update(status='skipped', scope='offline', reason='Explicit offline request')
        self.assertEqual(self.codes(), [])

    def test_legacy_record_remains_compatible(self):
        self.a['request'].pop('media_research_protocol')
        self.record.pop('schema_version')
        self.record.pop('needs')
        self.candidate.pop('verification')
        self.assertEqual(self.codes(), [])

    def test_tracking_parameters_do_not_create_independent_origins(self):
        self.assertEqual(original_key(dict(page_url='https://example.org/photo?utm_source=a#top')),
                         original_key(dict(page_url='https://example.org/photo?utm_source=b')))

    def test_distinct_originals_on_same_site_are_independent(self):
        self.assertNotEqual(original_key(dict(page_url='https://www.flickr.com/photos/fixture/12345/')),
                            original_key(dict(page_url='https://www.flickr.com/photos/fixture/12346/')))

    def test_commons_space_underscore_and_file_query_are_same_original(self):
        self.assertEqual(original_key(dict(page_url='https://commons.wikimedia.org/wiki/File:Test_photo.jpg')),
                         original_key(dict(page_url='https://commons.wikimedia.org/w/index.php?title=File:Test%20photo.jpg')))


if __name__ == '__main__':
    unittest.main()
