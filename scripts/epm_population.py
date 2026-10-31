"""Audited Actual EPM background subset; never relax selected-player import."""
from collections import Counter
from common import DataError, integer
from import_epm import normalize_actual_row, row_season, validate_import
from player_comparisons import full_table

POLICY='kaggle-v1-reference-concordance-2min'


def collect(bundle):
    # First replay the strictly accepted target contract. Population screens cannot
    # make a previously rejected target import eligible or change its metrics.
    validate_import(bundle)
    snapshot=bundle['epm_import']['snapshot']
    if snapshot['metadata'].get('source_kind')!='kaggle_deocheng_v1':
        raise DataError('New EPM population policy is restricted to reviewed Kaggle v1; other exports retain their declared precision')
    columns=snapshot['metadata']['columns'];base=full_table(bundle,'player_base','P_BASE')
    from advanced_percentiles import eligible
    checked=[];excluded=[];seen=set();sensitivity=Counter()
    for index,row in enumerate(snapshot['raw_rows'],1):
        if row_season(row[columns['season']],snapshot['metadata']['season_format'])!=bundle['season']:
            excluded.append(dict(row=index,reason='其他赛季，不纳入'));continue
        pid=integer(row[columns['nba_id']],'Actual population NBA ID')
        if pid in seen:raise DataError('Duplicate Actual EPM population ID')
        seen.add(pid)
        reference=base.get(pid)
        if reference is None:
            excluded.append(dict(row=index,player_id=pid,reason='参考联盟样本无此ID'));continue
        if not eligible(reference):
            excluded.append(dict(row=index,player_id=pid,reason='未达到GP/MIN门槛'));continue
        try:
            normalized=normalize_actual_row(snapshot,row,reference,population_policy=POLICY)
            if normalized['minutes']<500:raise DataError('提供者总分钟未达500门槛')
            checked.append(normalized)
            delta=normalized['minute_match']['absolute_difference']
            for limit in (.25,.5,1.0,2.0):
                if delta<=limit+1e-9:sensitivity[str(limit)]+=1
        except DataError as exc:
            excluded.append(dict(row=index,player_id=pid,reason=str(exc)))
    eligible_reference=sum(eligible(row) for row in base.values())
    return dict(rows=checked,excluded=excluded,policy=POLICY,raw_count=len(snapshot['raw_rows']),
                reference_eligible_count=eligible_reference,
                reference_coverage=len(checked)/eligible_reference if eligible_reference else None,
                exclusion_reasons=dict(Counter(row['reason'] for row in excluded)),
                sensitivity={str(limit):sensitivity[str(limit)] for limit in (.25,.5,1.0,2.0)},
                note='分钟差≤2只作经审查Kaggle v1的背景样本一致性筛选，不是精确导入、舍入证明或完整联盟认证。目标仍须通过原严格精度校验。')
