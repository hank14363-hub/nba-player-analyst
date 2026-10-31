"""Portable archives preserve source history and carry verifiable actual payloads."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError
from package_skill import build


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.root.mkdir()
        (self.root/'PACKAGE_INFO.json').write_text(json.dumps(dict(release_version='0.8.16',official_case='examples/current')))
        for name in ('SKILL.md','examples/current/report.md','examples/old/说明.md','tests/test_old.py','scripts/run.py'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name,encoding='utf-8')

    def test_runtime_omits_history_without_deleting_and_rehashes_readme(self):
        out=self.root.parent/'runtime.zip';result=build(self.root,out,'runtime')
        self.assertTrue((self.root/'examples/old/说明.md').exists())
        with ZipFile(out) as z:
            self.assertNotIn('nba-player-analyst/tests/test_old.py',z.namelist())
            self.assertIn('nba-player-analyst/examples/current/report.md',z.namelist())
            hashes=json.loads(z.read('nba-player-analyst/FILE_HASHES.json'))
            for path,value in hashes.items():self.assertEqual(hashlib.sha256(z.read('nba-player-analyst/'+path)).hexdigest(),value)
        self.assertEqual(result['omitted_files'],2)

    def test_full_roundtrips_unicode_and_history(self):
        out=self.root.parent/'full.zip';build(self.root,out)
        with ZipFile(out) as z:self.assertEqual(z.read('nba-player-analyst/examples/old/说明.md'),(self.root/'examples/old/说明.md').read_bytes())

    def test_output_collision_and_self_archive_rejected(self):
        with self.assertRaises(DataError):build(self.root,self.root/'bad.zip')
        out=self.root.parent/'full.zip';build(self.root,out)
        with self.assertRaises(DataError):build(self.root,out)

    def test_repeated_archives_are_deterministic(self):
        a=self.root.parent/'a.zip';b=self.root.parent/'b.zip'
        build(self.root,a);build(self.root,b)
        self.assertEqual(a.read_bytes(),b.read_bytes())
