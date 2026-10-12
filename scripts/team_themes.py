"""Editorial team-inspired palettes; not an official or historic brand registry."""
from __future__ import annotations
import re
from common import DataError

# Deliberately curated for high-contrast dark analysis cards, not licensed marks.
PALETTES = {
 'ATL':('#B91E35','#FFD35A'), 'BOS':('#087F54','#E8D7A2'),
 'BKN':('#3C424B','#F4F5F7'), 'CHA':('#216C83','#9BE4E6'),
 'CHI':('#BC163A','#F7E7DE'), 'CLE':('#741536','#F0C35C'),
 'DAL':('#1457AA','#9CCBF0'), 'DEN':('#17476B','#FEC84B'),
 'DET':('#BA2540','#84BAFF'), 'GSW':('#215BB9','#FFD348'),
 'HOU':('#B71B3C','#FFB8AA'), 'IND':('#274B85','#FFCE44'),
 'LAC':('#1F477A','#F77884'), 'LAL':('#55209A','#FFD447'),
 'MEM':('#465D91','#B7D8F0'), 'MIA':('#922345','#FFCD65'),
 'MIL':('#165F42','#E7DDB8'), 'MIN':('#154F73','#A8E348'),
 'NOP':('#223D63','#DAB97E'), 'NYK':('#225CA4','#FFAC61'),
 'OKC':('#1262A4','#FFB071'), 'ORL':('#155E9B','#B0D8FA'),
 'PHI':('#285CB0','#FF8691'), 'PHX':('#52278C','#FFB362'),
 'POR':('#B32337','#F6DCD8'), 'SAC':('#59318D','#D9C9EB'),
 'SAS':('#394856','#D0D6DF'), 'TOR':('#B02744','#F6C6CF'),
 'UTA':('#573287','#B5DBFF'), 'WAS':('#254A73','#FC9EAD'),
 'NEUTRAL':('#334155','#D1DBE8'),
}
TEAM_IDS = {
 1610612737:'ATL',1610612738:'BOS',1610612751:'BKN',1610612766:'CHA',1610612741:'CHI',
 1610612739:'CLE',1610612742:'DAL',1610612743:'DEN',1610612765:'DET',1610612744:'GSW',
 1610612745:'HOU',1610612754:'IND',1610612746:'LAC',1610612747:'LAL',1610612763:'MEM',
 1610612748:'MIA',1610612749:'MIL',1610612750:'MIN',1610612740:'NOP',1610612752:'NYK',
 1610612760:'OKC',1610612753:'ORL',1610612755:'PHI',1610612756:'PHX',1610612757:'POR',
 1610612758:'SAC',1610612759:'SAS',1610612761:'TOR',1610612762:'UTA',1610612764:'WAS',
}
ALIASES = {'PHO':'PHX','BRK':'BKN','CHO':'CHA'}
HEX = re.compile(r'#[0-9a-fA-F]{6}\Z')


def rgb(value: str) -> tuple[int,int,int]:
    if not isinstance(value,str) or not HEX.fullmatch(value):
        raise DataError('Theme colors must be #RRGGBB; CSS expressions are not accepted')
    return tuple(int(value[i:i+2],16) for i in (1,3,5))


def luminance(value: str) -> float:
    def linear(v):
        v /= 255
        return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    r,g,b=map(linear,rgb(value))
    return .2126*r+.7152*g+.0722*b


def contrast(a: str,b: str) -> float:
    x,y=sorted((luminance(a),luminance(b)))
    return (y+.05)/(x+.05)


def foreground(bg: str) -> str:
    return max(('#FFFFFF','#10141B'),key=lambda c:contrast(c,bg))


def select_theme(analysis: dict, name: str = 'auto', custom: dict | None = None) -> dict:
    selected=name.upper()
    reason='explicit_visual_override'
    if name.lower()=='auto':
        # Use player sample/reported label, NOT a hypothetical destination team.
        tid=analysis['sample'].get('player_team_id') or analysis['player'].get('reported_team_id')
        selected=TEAM_IDS.get(tid,'NEUTRAL')
        reason='player_sample_or_reported_team_label' if selected!='NEUTRAL' else 'unresolved_team_neutral'
    selected=ALIASES.get(selected,selected)
    if selected not in PALETTES:
        raise DataError('Unknown theme. Use auto, NEUTRAL or a supported NBA team abbreviation')
    primary,accent=PALETTES[selected]
    if custom is not None:
        if not isinstance(custom,dict) or set(custom)!={'primary','accent'}:
            raise DataError('Custom theme requires exactly primary and accent')
        primary,accent=custom['primary'],custom['accent']
        reason='explicit_custom_colors'
    rgb(primary);rgb(accent)
    bg,panel,text,muted='#11151C','#1B2029','#F3F5F8','#AAB4C2'
    if contrast(accent,bg)<4.5 or contrast(accent,panel)<4.5:
        raise DataError('Accent must meet 4.5:1 contrast on both dark canvas and cards')
    return {'key':selected,'primary':primary.upper(),'accent':accent.upper(),
            'on_primary':foreground(primary),'on_accent':foreground(accent),
            'background':bg,'panel':panel,'text':text,'muted':muted,'grid':'#3D4655',
            'selection_reason':reason,'scope':'editorial_palette_only_not_a_team_membership_claim',
            'official_brand_specification':False}


def css_vars(theme: dict) -> str:
    fields=('primary','accent','on_primary','on_accent','background','panel','text','muted','grid')
    return ':root{' + ''.join('--'+k.replace('_','-')+':'+theme[k]+';' for k in fields) + '}'
