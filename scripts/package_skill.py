"""Build full or runtime ZIPs without changing or deleting historical source files."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
from common import DataError,SKILL_ROOT,read_json

IGNORED={'.git','__pycache__','.pytest_cache','.venv','node_modules'}


def entries(root,profile):
    if profile not in ('full','runtime'):raise DataError('Unknown distribution profile')
    root=Path(root).resolve();info=read_json(root/'PACKAGE_INFO.json')
    current=info['official_case'].split('/')[1]
    retained={current,'demo_output','demo_csv','demo_bundle.json'}
    selected={};omitted=[]
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root);name=relative.as_posix()
        if any(part in IGNORED for part in relative.parts):continue
        if path.is_symlink():raise DataError('Archive symlinks are unsupported: '+name)
        if not path.is_file() or name in ('FILE_HASHES.json','DISTRIBUTION.json'):continue
        if profile=='runtime' and (relative.parts[0]=='tests' or
                (relative.parts[0]=='examples' and len(relative.parts)>1 and relative.parts[1] not in retained)):
            omitted.append(name);continue
        selected[name]=path.read_bytes()
    if profile=='runtime':
        selected['README.md']=('''# NBA Player Analyst v'''+info['release_version']+'''

运行版：包含全部运行脚本、资源、方法文档、当前真实示例及合成结构示例。
将整个 nba-player-analyst 文件夹放入 skills 目录，按 [SKILL.md](SKILL.md) 执行。

- [当前库里示例](examples/'''+current+'''/research_book.html)：旧证据重放，非新取数；正文和照片保留日期与来源。
- [入口说明](START_HERE.md)、[数据来源](references/data_sources.md)、[百分位规则](references/advanced_percentiles.md)。
- 历史案例和 tests 未包含。文档中的历史案例路径只适用于完整包；运行完整回归请使用 full ZIP。
- 运行脚本及统计逻辑与完整包一致；当前示例保留原始数据、claims、正文、配图和长图。

DISTRIBUTION.json 列出实际文件摘要和省略项。此包不删除完整源目录的任何文件。
''').encode('utf-8')
        selected['START_HERE.md']=('''# 从这里开始 · v'''+info['release_version']+'''

这是运行版分发包，安装与范围见 [README.md](README.md)。执行流程见 [SKILL.md](SKILL.md)。
历史目录和回归测试请从同版本完整包获取；不将其省略解释为验证失败或当前接口状态。
''').encode('utf-8')
    return selected,omitted


def build(root,out,profile='full'):
    root=Path(root).resolve();out=Path(out).resolve()
    if out.is_relative_to(root):raise DataError('ZIP output must be outside Skill source directory')
    if out.exists():raise DataError('Refusing to overwrite an existing distribution')
    selected,omitted=entries(root,profile)
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in selected.items()}
    manifest=dict(release_version=read_json(root/'PACKAGE_INFO.json')['release_version'],profile=profile,
        file_count=len(selected),uncompressed_bytes=sum(map(len,selected.values())),sha256=hashes,
        omitted=omitted,note='Hashes cover payload files; manifest and FILE_HASHES are excluded from their own hashes. Runtime omits historical examples and regression tests.')
    selected['FILE_HASHES.json']=json.dumps(hashes,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
    selected['DISTRIBUTION.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
    out.parent.mkdir(parents=True,exist_ok=True)
    released=read_json(root/'PACKAGE_INFO.json').get('released_on','2026-10-22')
    stamp=tuple(map(int,released.split('-')))+(0,0,0)
    with ZipFile(out,'x',compression=ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(selected.items()):
            item=ZipInfo('nba-player-analyst/'+name,date_time=stamp)
            item.compress_type=ZIP_DEFLATED;item.external_attr=0o100644<<16
            archive.writestr(item,data,compress_type=ZIP_DEFLATED,compresslevel=9)
    with ZipFile(out) as archive:
        if archive.testzip():raise DataError('Distribution CRC check failed')
        for name,expected in hashes.items():
            if hashlib.sha256(archive.read('nba-player-analyst/'+name)).hexdigest()!=expected:
                raise DataError('Distribution hash mismatch: '+name)
    return dict(profile=profile,path=str(out),files=len(selected),uncompressed_bytes=manifest['uncompressed_bytes'],zip_bytes=out.stat().st_size,
        sha256=hashlib.sha256(out.read_bytes()).hexdigest(),omitted_files=len(omitted))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=SKILL_ROOT)
    parser.add_argument('--profile',choices=('full','runtime'),default='full')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.root,args.out,args.profile),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
