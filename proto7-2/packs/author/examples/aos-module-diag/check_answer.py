"""獨立核對 pending／halted／inflight 的固定答案與唯讀。"""
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
    entry = Path(top)/'modules/llmdiag/aos7-llmdiag'
    expected = dict(v=1,
        llmcall_pending=[dict(budget='llm',call_id=c,stage=s) for c,s in
                         [('badraw','raw'),('pendingraw','raw'),('pendingreq','request')]],
        author_halted=[dict(job=j,rid=j.rsplit('_',1)[0],kind='unknown',why='pending llmcall') for j in
                       ['a_req_89abcdef','my_req_0123abcd','z_req_aabbccdd']],
        budget_inflight=[dict(budget=b,inflight=n) for b,n in [('abusy',2),('busy',3),('zbusy',7)]])
    def run(path):
        p = subprocess.run([sys.executable,str(entry),str(path)],capture_output=True,timeout=30)
        if snapshot(node) != before:
            issues.append('fixture 目錄、檔案位元組或權限被修改')
        return p
    try:
        p = run(node)
        if p.returncode or len(p.stdout.splitlines()) != 1 or not exact(json.loads(p.stdout),expected):
            issues.append('答案、型別或退出碼不合：' + p.stdout.decode('utf-8','replace'))
        with tempfile.TemporaryDirectory() as tmp:
            for path in (Path(tmp)/'absent',Path(tmp)/'file'):
                if path.name == 'file':
                    path.write_text('not a directory')
                if run(path).returncode != 2:
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
