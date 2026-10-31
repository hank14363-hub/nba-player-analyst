"""Create a local image-search plan, never a search result or download claim."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from common import DataError, now_iso, read_json, validate_season, write_json

PROTOCOL = '0.2.0'
SLOTS = ('cover', 'scoring', 'creation', 'defense')
TERMS = dict(cover='portrait headshot', scoring='shooting driving layup',
             creation='passing dribbling pick and roll', defense='defending contest rebound')


def build_plan(analysis, team='', aliases=(), slots=SLOTS, include_animation=False):
    player = analysis['player']
    sample = analysis['sample']
    validate_season(sample['season'], sample['season_type'])
    name = player['name'].strip()
    if not name:
        raise DataError('Image research needs the verified player name.')
    if not slots or any(slot not in SLOTS for slot in slots) or len(slots) != len(set(slots)):
        raise DataError('Choose unique supported media slots.')
    if len(aliases) > 8 or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
        raise DataError('Use up to eight verified, nonempty name aliases.')
    identity = dict(player_id=player['id'], season=sample['season'], season_type=sample['season_type'])
    start = int(sample['season'][:4])
    years = [str(start), str(start + 1)]
    names = list(dict.fromkeys([name] + [alias.strip() for alias in aliases]))
    # A reported/current team is deliberately not used to label a past season or a traded player's full season.
    scope = 'playoffs' if sample['season_type'] == 'Playoffs' else 'regular season'
    prefix = ' '.join(filter(None, [f'"{name}"', team.strip()]))
    queries = []

    def add(route, query, purpose):
        if any(row['query'] == query for row in queries):
            return
        queries.append(dict(id=f'Q{len(queries)+1:03}', route=route, query=query,
                            purpose=purpose, status='not_executed'))

    for year in years:
        add('discovery', f'{prefix} {year} {scope} photo', '核对跨年赛季的身份、球队与事件日期')
    add('commons', f'site:commons.wikimedia.org "{name}" {years[0]}', '先读文件页及人物分类；不是缩略图许可')
    add('commons', f'site:commons.wikimedia.org "{name}" {years[1]}', '查找赛季第二自然年的原始文件页')
    add('flickr', f'site:flickr.com/photos "{name}" {sample["season"]}', '寻找摄影者原作；逐项核验许可与拍摄日期')
    for slot in slots:
        add('purpose', f'{prefix} {sample["season"]} {TERMS[slot]} photo', f'{slot}用途；并非能力或回合证据')
    for alias in names[1:]:
        add('alias', f'"{alias}" {sample["season"]} photo 图片', '确认别名确为同一NBA ID，不只搜中文译名')
    add('creator', f'"{name}" basketball photographer Creative Commons', '扩展独立摄影者及明确可复用作品')
    add('official_reference', f'{prefix} {sample["season"]} NBA team photo gallery', '官方页仅发现/身份日期核对；不视为下载许可')
    add('historical_fallback', f'"{name}" portrait Creative Commons', '本季不足时寻找明确年份的资料照并可见披露')
    if include_animation:
        add('animation_optional', f'{prefix} {sample["season"]} basketball clip license',
            '仅相关且许可适用的实际片段；找不到则用静态照，不抓取平台视频')
    routes = [
        dict(id='commons', url='https://commons.wikimedia.org/w/index.php?' + urlencode(dict(
            title='Special:MediaSearch', type='image', search=name)),
             use='公开图库入口；打开具体File页检查作者、许可与日期'),
        dict(id='flickr', url='https://www.flickr.com/search/?' + urlencode(dict(text=name)),
             use='摄影者原作入口；搜索页不保证CC，必须回到单张作品页'),
        dict(id='openverse', url='https://openverse.org/search/image?' + urlencode(dict(q=name)),
             use='许可素材索引，只作发现；回到原始发布者核对，不把索引声明当最终许可'),
    ]
    return dict(schema_version='0.1.0', research_protocol=PROTOCOL, status='not_executed',
                generated_at=now_iso(), identity=identity, player_name=name,
                verified_team_hint=team.strip() or None, calendar_years=years,
                note='仅生成查询建议；未联网、未搜索、未核验或下载。赛季两个自然年不等于精确比赛日期。',
                needs=[dict(slot=slot, purpose=TERMS[slot], priority='primary' if slot == 'cover' else 'optional')
                       for slot in slots], suggested_queries=queries, discovery_routes=routes,
                suggested_budget=dict(first_pass_queries='4–6', expanded_total_queries='8–12',
                                      original_pages='6–12', policy='建议上限可随范围调整；满足用途后停止，不逐条强制执行。'),
                date_warning='核对真实赛程；停摆、疫情或特殊赛季可能不在通常月份。不能从当前球队推定历史效力球队。')


def record_template(plan):
    return dict(schema_version=PROTOCOL, identity=plan['identity'], status='pending', reason='',
                queries=[], candidates=[], needs=[dict(slot=n['slot'], status='pending',
                    reason='', media_ids=[]) for n in plan['needs']], stop_reason='')


def plan_markdown(plan):
    lines = ['# 图片检索计划（尚未执行）', '', plan['note'], '',
             f'球员：{plan["player_name"]}；赛季：{plan["identity"]["season"]}；'
             f'类型：{plan["identity"]["season_type"]}', '', plan['date_warning'], '',
             '先用4–6条高价值查询，来源不足再扩展；通常总计8–12条、查阅6–12个原页即可评估。'
             '这是工作预算，不是必须凑满的结果数量。', '', '## 建议查询', '']
    for row in plan['suggested_queries']:
        lines += [f'- {row["id"]} [{row["route"]}] `{row["query"]}` — {row["purpose"]}']
    lines += ['', '## 正常公开检索入口', '']
    for route in plan['discovery_routes']:
        lines += [f'- [{route["id"]}]({route["url"]})：{route["use"]}']
    lines += ['', '## 完成条件', '',
              '实际执行后才把查询写入media_research.json；逐用途登记covered/unavailable/not_needed及原因。'
              '采用前核对身份、日期、权利、实际画面和本地文件。完整步骤见references/image_research.md。', '']
    return '\n'.join(lines)


def write_plan(run_dir, analysis, *, force=False, **options):
    paths = [run_dir / name for name in ('media_search_plan.json', 'media_search_plan.md', 'media_research.template.json')]
    if not force and any(path.exists() for path in paths):
        raise DataError('Image plan already exists; --force replaces only plan/template files, never actual research logs.')
    plan = build_plan(analysis, **options)
    write_json(paths[0], plan)
    paths[1].write_text(plan_markdown(plan), encoding='utf-8')
    write_json(paths[2], record_template(plan))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--team', default='', help='Verified historical team/stint; never inferred from current team')
    parser.add_argument('--alias', action='append', default=[], help='Verified alternate name; repeatable')
    parser.add_argument('--slots', nargs='+', choices=SLOTS, default=list(SLOTS))
    parser.add_argument('--animation', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    try:
        plan = write_plan(args.run_dir, read_json(args.run_dir / 'analysis.json'), force=args.force,
                          team=args.team, aliases=args.alias, slots=args.slots, include_animation=args.animation)
        print(json.dumps(dict(status=plan['status'], queries_suggested=len(plan['suggested_queries']),
                              network_requests=0, actual_research_log_modified=False), ensure_ascii=False))
    except (DataError, OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
