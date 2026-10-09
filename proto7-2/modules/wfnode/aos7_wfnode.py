"""node 工作流導入、衛生檢查與續行點。"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

from wfnode_fill import fill_text
from wfnode_state import NEXT, atomic_write, state


def markdowns(node):
    for root, dirs, files in os.walk(node):
        dirs[:] = sorted(d for d in dirs if d != '.git')
        for name in sorted(files):
            if name.endswith('.md'):
                yield Path(root) / name


ROSTER = '''# ROSTER — 誰在線上、各自是誰

動工前在「現役成員」下追加自己那一格，不改別人的；收線把狀態改「已收線（日期）」。

## 格式

```markdown
### 成員名稱
- 狀態：
- 我是誰：
- 團隊：
- 上游：
- 領地：
- 答得出什麼：
- 答不出什麼：
- 怎麼找我：
```

## 現役成員

（目前無）
'''


def supplement(node):
    table = {'contract': 'wf-table/1', 'source': 'ROSTER.md',
             'extracted': dt.date.today().isoformat(),
             'columns': ['線名', '狀態', '持有', '唯讀禁區', '登記時間', '收線證據'], 'rows': []}
    for rel, content in [('handoffs/NEXT-SESSION.md', NEXT), ('ROSTER.md', ROSTER),
                         ('line-claims.json', json.dumps(table, indent=1, ensure_ascii=False) + '\n')]:
        path = node / 'wf' / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            publish_missing(path, content)
        except FileExistsError:
            pass


def lint(node):
    result = subprocess.run(['bash', str(node / 'wf/tools/wf-lint.sh'), str(node)],
                            capture_output=True, text=True)
    output = result.stdout + result.stderr
    totals = re.findall(r'TOTAL broken=(\d+)', output)
    failed = result.returncode != 0 or not totals or int(totals[-1]) > 0
    if failed:
        broken = [line for line in output.splitlines() if 'BROKEN' in line]
        print('\n'.join(broken) if broken else output or '工作流檢查未完成')
    warnings = any(int(value) > 0 for value in re.findall(
        r'\b(?:oversize|biglist|biglist_links|querycmd)=(\d+)',
        '\n'.join(line for line in output.splitlines() if 'SUMMARY' in line)))
    if not failed and warnings:
        print(output, end='' if output.endswith('\n') else '\n')
    return failed


def scan(node, marker):
    return [(str(path.relative_to(node)), number, line)
            for path in markdowns(node)
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
            if marker in line]


def init(node, flavor=None):
    home = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()
    script = home / 'tools/wf-init.sh'
    if not script.is_file():
        import sys
        print('找不到 workflows，請設 AOS7_WF_HOME 或 clone workflows。', file=sys.stderr)
        return 2
    if re.search(r'[\[\]{}()<>|`*\\\r\n]', node.name):
        import sys
        print('node 名只能用一般字元', file=sys.stderr)
        return 2
    node.mkdir(parents=True, exist_ok=True)
    if (node / 'AGENTS.md').exists():
        print('已導入過，只補缺檔')
        fill_node(node, node.name)
        supplement(node)
    else:
        temp = node / '.wfnode-tmp'
        shutil.rmtree(temp, ignore_errors=True)
        staged = temp / node.name
        try:
            command = ['bash', str(script), '--target', str(staged), '--non-invasive', 'wf']
            if flavor is not None:
                command += ['--flavor', flavor]
            result = subprocess.run(command + ['--quiet'], capture_output=True, text=True)
            if result.returncode:
                import sys
                print(result.stderr, end='', file=sys.stderr)
                return 1
            fill_node(staged, node.name)
            supplement(staged)
            for item in sorted(staged.iterdir(), key=lambda p: (p.name == 'AGENTS.md', p.name)):
                merge_missing(item, node / item.name)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    if lint(node):
        return 1
    unknown = sum(line.count('（未定：') for _, _, line in scan(node, '（未定：'))
    decisions = scan(node, '〔導入判斷〕')
    residue = scan(node, '{{')
    print(f'node：{node}\n{{{{ 剩 {sum(line.count("{{") for _, _, line in residue)}；未定 {unknown} 處')
    print(f'待人決定 {len(decisions)} 段')
    for path, number, _ in decisions:
        print(f'{path}:{number}')
    print(f'下一步：aos7-wfnode check {shlex.quote(str(node))}')
    return int(bool(residue))


def check(node):
    if not (node / 'wf/tools/wf-lint.sh').is_file():
        print('還沒 init')
        return 2
    failed = lint(node)
    for name in ('SESSION-LOG.md', 'WAIT_USER.md'):
        path = node / 'wf' / name
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        entries = [(i, line) for i, line in enumerate(lines, 1) if re.match(r'^- \[', line)]
        print(f'{name}：open 項 {len(entries)}')
        for number, line in entries:
            if re.search(r'^- \[[xX✓✔]\]|✅|✔|~~|已完成|已結案|已收線|（完成）|\(done\)|\[done\]|DONE', line):
                print(f'{name}:{number}: {line}\n做完就刪掉這行（歷史在 git log）')
                failed = True
    for path, number, line in scan(node, '{{'):
        print(f'{path}:{number}: {line}')
        failed = True
    if not failed:
        print('OK：連結、活狀態與佔位檢查通過')
    return int(failed)


def fill_node(node, name):
    for path in markdowns(node):
        text = path.read_text(encoding='utf-8')
        filled = fill_text(text, name, index=path == node / 'wf/INDEX.md')
        if filled != text:
            atomic_write(path, filled)


def merge_missing(source, dest):
    if not dest.exists():
        os.replace(source, dest)
    elif source.is_dir() and dest.is_dir():
        for item in source.iterdir():
            merge_missing(item, dest / item.name)


def publish_missing(path, content):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.wfnode-', delete=False) as stream:
            temp = stream.name
            stream.write(content)
        os.link(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
