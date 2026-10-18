"""Embed attributed local raster assets. Media illustrates the article, never proves a metric."""
import base64
import hashlib
import html
import re
from pathlib import Path
from common import DataError, read_json


def raster(run_dir, relative, expected):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise DataError('Media path must be a local relative POSIX path.')
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise DataError('Media cannot escape the run directory.')
    target=(run_dir/path).resolve()
    if not target.is_relative_to(run_dir.resolve()):
        raise DataError('Media symlink escapes the run directory.')
    data=target.read_bytes()
    if len(data)>8_000_000:
        raise DataError('Media asset exceeds 8 MB; use a smaller raster export.')
    if not isinstance(expected,str) or hashlib.sha256(data).hexdigest()!=expected:
        raise DataError('Media checksum mismatch: '+relative)
    if data.startswith(b'\xff\xd8\xff'): mime='image/jpeg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'): mime='image/png'
    elif data.startswith((b'GIF87a',b'GIF89a')): mime='image/gif'
    else:raise DataError('Only JPEG/PNG/GIF raster media is supported; no executable SVG or remote loading.')
    return 'data:'+mime+';base64,'+base64.b64encode(data).decode(), len(data)


def load_media(run_dir, analysis):
    path=run_dir/'media_content.json'
    if not path.exists():return [],[]
    content=read_json(path)
    expected=dict(player_id=analysis['player']['id'],season=analysis['sample']['season'],season_type=analysis['sample']['season_type'])
    if content.get('schema_version')!='0.1.0' or content.get('identity')!=expected:
        raise DataError('Media identity/schema differs from this research book.')
    rows=content.get('items')
    if not isinstance(rows,list):raise DataError('Media items must be a list.')
    ids=set();assets=['media_content.json'];result=[];total=0
    for row in rows:
        if not isinstance(row,dict):raise DataError('Media item must be an object.')
        mid=row.get('id','')
        if not isinstance(mid,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',mid) or mid in ids:
            raise DataError('Media requires a unique safe ID.')
        ids.add(mid)
        if row.get('slot') not in {'cover','scoring','creation','defense'} or row.get('kind') not in {'photo','photo_slideshow','game_clip'}:
            raise DataError('Unsupported media slot/kind.')
        for field in ('title','alt','caption'):
            if not isinstance(row.get(field),str) or not row[field].strip():raise DataError('Media lacks '+field)
        sids=row.get('source_ids')
        if not isinstance(sids,list) or not sids or any(sid not in analysis['sources'] for sid in sids):
            raise DataError('Media needs registered source IDs.')
        for sid in sids:
            source=analysis['sources'][sid]
            if source.get('status','ok')!='ok' or source.get('source_type')!='illustrative_media' or not source.get('credit') or not source.get('license'):
                raise DataError('Media source needs credit, license and illustrative_media definition.')
        data,size=raster(run_dir,row.get('path'),row.get('sha256'));total+=size
        if row['kind']=='photo' and data.startswith('data:image/gif;'):
            raise DataError('GIF needs an animated kind with a static fallback and playback control.')
        item=dict(row,data_url=data)
        assets.append(row['path'])
        if row['kind']!='photo':
            poster,size=raster(run_dir,row.get('poster_path'),row.get('poster_sha256'));total+=size
            if not data.startswith('data:image/gif;') or poster.startswith('data:image/gif;'):
                raise DataError('Animated media needs a GIF and static PNG/JPEG fallback.')
            item['poster_data_url']=poster;assets.append(row['poster_path'])
        result.append(item)
    if total>12_000_000:raise DataError('Combined embedded media exceeds 12 MB.')
    return result,list(dict.fromkeys(assets))


def render_media(item,sources):
    esc=lambda v:html.escape(str(v),quote=True)
    animated=item['kind']!='photo'
    src=item['poster_data_url'] if animated else item['data_url']
    extra=' data-animated-src="'+item['data_url']+'" data-poster-src="'+src+'"' if animated else ''
    badge='照片轮播 GIF' if item['kind']=='photo_slideshow' else ('比赛片段 GIF' if animated else '影像资料')
    figure='<figure class="court-media" id="media-'+esc(item['id'])+'"><div class="media-frame"><img src="'+src+'"'+extra+' alt="'+esc(item['alt'])+'" decoding="async" loading="lazy"><span class="media-badge">'+badge+'</span></div>'
    figure+='<figcaption><div class="media-title">'+esc(item['title'])+'</div><p>'+esc(item['caption'])+'</p><div class="media-credit">'
    figure+=' · '.join(esc(sources[s]['credit'])+' / '+esc(sources[s]['license']) for s in item['source_ids'])
    figure+=' '+ ' '.join('<a class="source-ref" href="#source-'+esc(s)+'">图片出处 ↗</a>' for s in item['source_ids'])+'</div>'
    if animated:
        label='动态照片' if item['kind']=='photo_slideshow' else '比赛片段'
        figure+='<button class="media-toggle" type="button" aria-pressed="false" data-play-label="播放'+label+'" data-pause-label="暂停'+label+'">播放'+label+'</button>'
    return figure+'</figcaption></figure>'
