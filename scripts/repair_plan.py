"""Generate reviewable PowerShell commands; never execute them automatically."""
from pathlib import Path
import sys
from common import SKILL_ROOT, TABLES

def command(argv):
    return '& '+' '.join("'"+str(v).replace("'","''")+"'" for v in argv)

def new_destination(path):
    candidate=path
    n=1
    while candidate.exists():
        candidate=path.with_name(path.name+'-'+str(n));n+=1
    return candidate

def plan(bundle,analysis,out):
    out=Path(out).resolve();commands=[];blocked=[]
    for table,(sid,_) in TABLES.items():
        if table not in bundle['tables'] or bundle['tables'][table]:continue
        if bundle.get('data_kind')=='synthetic' or bundle.get('sumitro_import') is not None or bundle.get('kaggle_import') is not None:
            blocked.append(dict(table=table,reason='Provider-specific import; do not automatically mix official NBA rows into retained import contracts.'));continue
        destination=new_destination(out.parent/(out.name+'-repair-'+table))
        argv=[sys.executable,str(SKILL_ROOT/'scripts/repair_data.py'),'--input',str(out/'data_bundle.json'),'--tables',table,'--out',str(destination)]
        if table in ('player_onoff','player_shots'):argv+=['--player-id',str(analysis['player']['id'])]
        if table=='player_onoff':
            team=analysis['request'].get('on_off_team_id',0)
            if not team:
                blocked.append(dict(table=table,reason='Actual On/Off team not recorded; specify and verify team ID before repair.'));continue
            argv+=['--on-off-team-id',str(team)]
        commands.append(dict(table=table,reason=bundle['sources'].get(sid,{}).get('reason','Missing source rows'),argv=argv,powershell=command(argv)))
    return dict(status='commands_available' if commands else 'no_commands',automatic_execution=False,commands=commands,blocked=blocked,note='Run each command separately, then re-analyze the repaired bundle and re-audit claims. Commands use new output directories; they are not chained merges.')
