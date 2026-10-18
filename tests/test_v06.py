import base64,copy,hashlib,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError,read_json,write_json
from book_media import load_media,render_media
from calculate_metrics import analyze
from book_sources import source_index
from book_visuals import visuals
from team_themes import select_theme
from html.parser import HTMLParser
from render_research_book import Book
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a90AAAAAASUVORK5CYII=')

class MediaEvidence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.a=analyze(read_json(ROOT/'examples/demo_bundle.json'),dict(player='MVP Demo Guard',season='2024-25',season_type='Regular Season',team_id=0))
        self.a['sources']['EXT_PHOTO']=dict(provider='Synthetic test',source_type='illustrative_media',status='ok',credit='Synthetic fixture',license='Synthetic fixture',url='https://example.com/fixture')
        (self.path/'image.png').write_bytes(PNG)
        self.c=dict(schema_version='0.1.0',identity=dict(player_id=self.a['player']['id'],season='2024-25',season_type='Regular Season'),items=[dict(id='image',slot='cover',kind='photo',path='image.png',title='Synthetic',alt='Synthetic image',caption='Synthetic fixture only',source_ids=['EXT_PHOTO'],sha256=hashlib.sha256(PNG).hexdigest())])
    def tearDown(self):self.temp.cleanup()
    def load(self):
        write_json(self.path/'media_content.json',self.c)
        return load_media(self.path,self.a)
    def test_offline_media_preserves_source_and_embeds_raster(self):
        items,files=self.load()
        html=render_media(items[0],self.a['sources'])
        self.assertIn('src="data:image/png;base64,',html)
        self.assertIn('#source-EXT_PHOTO',html)
        self.assertIn('media_content.json',files)
        self.assertNotIn('src="http',html)
    def test_changed_image_checksum_rejected(self):
        (self.path/'image.png').write_bytes(PNG+b'changed')
        with self.assertRaises(DataError):self.load()
    def test_media_cannot_escape_or_load_remote_url(self):
        for path in ['../image.png','https://example.com/photo.png','C:/secret.png','folder\\photo.png']:
            with self.subTest(path=path):
                self.c['items'][0]['path']=path
                with self.assertRaises(DataError):self.load()
    def test_executable_svg_rejected_even_with_matching_checksum(self):
        svg=b'<svg onload="alert(1)"/>'
        (self.path/'image.png').write_bytes(svg)
        self.c['items'][0]['sha256']=hashlib.sha256(svg).hexdigest()
        with self.assertRaises(DataError):self.load()
    def test_gif_cannot_silently_autoplay_as_photo(self):
        gif=b'GIF89a'+b'fixture'
        (self.path/'image.png').write_bytes(gif)
        self.c['items'][0]['sha256']=hashlib.sha256(gif).hexdigest()
        with self.assertRaises(DataError):self.load()
    def test_unregistered_source_rejected(self):
        self.c['items'][0]['source_ids']=['EXT_UNKNOWN']
        with self.assertRaises(DataError):self.load()
    def test_illustration_cannot_borrow_statistical_source(self):
        self.c['items'][0]['source_ids']=['P_BASE']
        with self.assertRaises(DataError):self.load()
    def test_mismatched_player_rejected(self):
        self.c['identity']['player_id']+=1
        with self.assertRaises(DataError):self.load()


class MediaPlacement(unittest.TestCase):
    """Pictures belong to their themes, including when the full article is folded."""
    def test_each_slot_is_visible_once_in_both_layouts(self):
        case=ROOT/'examples/cade-cunningham-2024-25-official-v081'
        analysis=read_json(case/'analysis.json')
        analysis['sources'].update(read_json(case/'sources.json')['sources'])
        claims=read_json(case/'claims.json')
        content=read_json(case/'book_content.json')
        media,_=load_media(case,analysis)
        # Reuse a fixture image only to exercise the otherwise empty defense slot.
        defense=copy.deepcopy(next(m for m in media if m['slot']=='scoring'))
        defense.update(id='defense-fixture',slot='defense')
        media.append(defense)

        class Placement(HTMLParser):
            def __init__(self):
                super().__init__();self.sections=[];self.details=[];self.figures=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='section':self.sections.append(attrs.get('id',''))
                if tag=='details':self.details.append('open' in attrs)
                if tag=='figure' and 'court-media' in attrs.get('class','').split():
                    module=next((s for s in reversed(self.sections) if s.startswith('module-')), 'cover')
                    self.figures.append((attrs['id'],module,all(self.details)))
            def handle_endtag(self,tag):
                if tag=='section':self.sections.pop()
                if tag=='details':self.details.pop()

        for integrated in (True,False):
            with self.subTest(integrated=integrated):
                book_content=copy.deepcopy(content)
                if integrated:book_content['presentation']='integrated'
                else:book_content.pop('presentation',None)
                rendered=Book(analysis,claims,book_content,'',media=media).render()
                parsed=Placement();parsed.feed(rendered)
                expected={'cover':'cover','scoring':'module-02','creation':'module-03','defense':'module-04'}
                self.assertCountEqual(parsed.figures,[(('media-'+m['id']),expected[m['slot']],True) for m in media])
                self.assertNotIn('class="historical-media"',rendered)

    def test_no_images_do_not_create_an_empty_gallery(self):
        case=ROOT/'examples/cade-cunningham-2024-25-official-v081'
        analysis=read_json(case/'analysis.json')
        analysis['sources'].update(read_json(case/'sources.json')['sources'])
        rendered=Book(analysis,read_json(case/'claims.json'),read_json(case/'book_content.json'),'').render()
        self.assertNotIn('class="historical-media"',rendered)
        self.assertNotIn('class="court-media"',rendered)


class SourcePresentation(unittest.TestCase):
    def setUp(self):
        self.a=analyze(read_json(ROOT/'examples/demo_bundle.json'),dict(player='MVP Demo Guard',season='2024-25',season_type='Regular Season',team_id=0))
    def test_full_source_url_is_kept_without_becoming_display_text(self):
        url='https://example.com/data?long_parameter=original_scope'
        self.a['sources']['P_BASE']['url']=url
        out=source_index(self.a)
        self.assertIn('href="'+url+'"',out)
        self.assertNotIn('>'+url+'<',out)
        self.assertIn('id="source-P_BASE"',out)
    def test_bad_source_protocol_is_not_active(self):
        self.a['sources']['P_BASE']['url']='javascript:alert(1)'
        self.assertNotIn('href="javascript:',source_index(self.a))
    def test_book_chart_colors_do_not_change_source_metrics(self):
        before=copy.deepcopy(self.a)
        chart=visuals(self.a,select_theme(self.a))['efficiency']['svg']
        self.assertNotIn('#1B2029',chart)
        self.assertNotIn('#F3F5F8',chart)
        self.assertEqual(self.a,before)
