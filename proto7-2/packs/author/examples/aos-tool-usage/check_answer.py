"""固定答案獨立核對 day／hour、缺口與唯讀；不 import 候選。"""
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


def snapshot(node):
    return {p.relative_to(node).as_posix(): ('dir' if p.is_dir() else 'file',
            None if p.is_dir() else p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
            for p in [node, *node.rglob('*')]}


def exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def check_answer(top, fixture):
    node = Path(fixture)
    before, issues = snapshot(node), []
    entry = Path(top) / 'packs/usage/bin/aos7-usage'
    def group(model, holder, period, calls, used, overrun=0):
        return dict(model=model, holder=holder, period=period, calls=calls, used=used, overrun=overrun)
    sol, astra = 'chatgpt-gpt-6-sol', 'chatgpt-gpt-6-astra'
    day = [group(astra,'planner','2026-10-08',1,50,10), group(sol,'author','-',4,34),
           group(sol,'author','2026-10-08',4,673), group(sol,'author','2026-10-09',1,100),
           group('fake','author','-',1,7)]
    hour = [group(astra,'planner','2026-10-08T10',1,50,10), group(sol,'author','-',4,34),
            group(sol,'author','2026-10-08T10',2,643), group(sol,'author','2026-10-08T11',2,30),
            group(sol,'author','2026-10-09T03',1,100), group('fake','author','-',1,7)]
    budgets = {b: dict(receipts_used=u,ledger_used=l,diff=d) for b,u,l,d in
               [('b2',5,None,None),('bbool',3,None,None),('bneg',17,5,-12),
                ('btext',9,None,None),('llm',830,900,70)]}
    gaps = [dict(budget='llm',call_id=cid,why=why) for cid,why in
            [('c10','bad_json'),('c11','bad_json'),('c3','overrun'),('c4','no_receipt'),('c5','bad_json')]]
    def run(args):
        p = subprocess.run([sys.executable,str(entry),*args],capture_output=True,timeout=30)
        if snapshot(node) != before:
            issues.append('fixture 目錄、檔案位元組或權限被修改')
        return p
    try:
        for by, args, groups in [('day',[],day),('day',['--by','day'],day),('hour',['--by','hour'],hour)]:
            p = run([str(node),*args])
            expected = dict(v=1,by=by,groups=groups,budgets=budgets,gaps=gaps)
            if p.returncode or len(p.stdout.splitlines()) != 1 or not exact(json.loads(p.stdout),expected):
                issues.append(by + ' 答案、型別或退出碼不合：' + p.stdout.decode('utf-8','replace'))
        with tempfile.TemporaryDirectory() as tmp:
            for path in (Path(tmp)/'absent', Path(tmp)/'file'):
                if path.name == 'file':
                    path.write_text('not a directory')
                if run([str(path)]).returncode != 2:
                    issues.append('非資料夾應退出 2')
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        issues.append(str(exc))
    if snapshot(node) != before:
        issues.append('fixture 目錄、檔案位元組或權限被修改')
    return dict(ok=not issues,issues=issues)


if __name__ == '__main__':
    answer = check_answer(*sys.argv[1:]) if len(sys.argv)==3 else dict(ok=False,issues=['用法：check_answer.py <proto7-2> <fixture>'])
    print(json.dumps(answer,ensure_ascii=False))
    raise SystemExit(0 if answer['ok'] else 1)
