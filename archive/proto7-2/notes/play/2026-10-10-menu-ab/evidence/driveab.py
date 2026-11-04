#!/usr/bin/env python3
"""用法：cwd=學徒 node（外部開 ledger），python3 -B driveab.py A|B TASK REP OUTDIR
[--model M] [--review R] [--tag T] [--offline]；已有 summary 退 2，不發布。
A 最多 6 輪，無 context/skills；B 沿原選單 max_rounds，退 3 最多執行兩次。
Token：兩組都採 llmcall 回條 used（實際結算 token，非字數估計）；
used 為 min(usage.total_tokens,reserve)，overrun 可能截斷；保留回條可追查。
A llm.used / review.llm.used；B state.calls[].used / 擷取 author review.llm.used。
used 缺失時記 token_missing，不以 0 假裝完整；offline 練習/規則用量為 0。
學徒 calls：A 有 llm.exit 的呼叫嘗試，B calls（含練習回覆、bad 重問）；不含審查。
A 格式規則固定為 text,json,schema,size：段頭錯/重複段名屬 text，缺段屬 schema。
B 格式阻擋為 gates 第 1 關次數 + log bad 次數。
內部 --capture KIND TARGET ... 透明擷取葉子原始輸出，不變更工具行為。
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

P = Path(__file__).resolve().parents[4]
SELF = Path(__file__).resolve()
AUTHOR = P / 'packs/author/bin/aos7-author'
MENU = P / 'packs/menu'
FORMAT_RULES = frozenset(('text', 'json', 'schema', 'size'))


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def execute(argv, dest, env=None):
    t = time.monotonic()
    call_env = dict(os.environ if env is None else env, PYTHONDONTWRITEBYTECODE='1')
    proc = subprocess.run(argv, capture_output=True, text=True, env=call_env)
    dest.with_suffix('.stdout').write_text(proc.stdout)
    dest.with_suffix('.stderr').write_text(proc.stderr)
    doc = {}
    for line in [proc.stdout] + list(reversed(proc.stdout.splitlines())):
        try:
            doc = json.loads(line)
            break
        except ValueError:
            pass
    dump(dest.with_suffix('.json'), dict(argv=argv, exit=proc.returncode,
         secs=time.monotonic()-t, result=doc))
    return proc.returncode, doc


def capture():
    kind, target = sys.argv[2:4]
    dest = Path(os.environ['AB_CAPTURE']) / (kind + '-' + str(time.time_ns()) + '-' + uuid.uuid4().hex[:8])
    proc = subprocess.run(['python3', '-B', target, *sys.argv[4:]], capture_output=True,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    dest.with_suffix('.stdout').write_bytes(proc.stdout)
    dest.with_suffix('.stderr').write_bytes(proc.stderr)
    dump(dest.with_suffix('.meta.json'), dict(exit=proc.returncode, argv=[target, *sys.argv[4:]]))
    if kind == 'tool':
        candidate = Path(sys.argv[5]) / 'candidate.txt'
        if candidate.exists():
            shutil.copyfile(candidate, dest.with_suffix('.candidate.txt'))
    sys.stdout.buffer.write(proc.stdout)
    sys.stderr.buffer.write(proc.stderr)
    return proc.returncode


def issues(check):
    return [i for g in check.get('gates', {}).values() for i in g.get('issues', [])]


def row(check, **extra):
    iss = issues(check)
    return dict(gate=check.get('failed_gate'), rules=sorted({i.get('rule') for i in iss if i.get('rule')}),
                issues=json.dumps(iss, ensure_ascii=False)[:300], **extra)


def tokens(info, missing, label):
    used = info.get('used')
    if isinstance(used, (int, float)) and not isinstance(used, bool):
        return used
    if info.get('exit') is not None:
        missing.append(label)
    return 0


def passed(check):
    return check.get('ok') is True and all(check.get('gates', {}).get(str(g), {}).get('ok') is True for g in (1, 2, 3))


def group_a(a, out, req, summary):
    prev = feedback = None
    for r in range(1, 7):
        cand = out / f'candidate-{r}.txt'
        cmd = ['python3', '-B', str(AUTHOR), 'propose', str(req)]
        if a.offline:
            cmd += ['--candidate', str(out/'valid.json'), '--reviewer', 'rules']
        else:
            cmd += ['--out', str(cand), '--llm', a.model, '--review-llm', a.review,
                    '--budget', 'budget/llm', '--deadline', '900', '--format', 'text',
                    '--call', f'{summary["rid"]}-r{r}-{uuid.uuid4().hex[:8]}']
            if prev:
                cmd += ['--previous', str(prev), '--feedback', str(feedback)]
        rc, doc = execute(cmd, out/f'propose-{r}')
        check = doc.get('check') or {}
        feedback = out / f'feedback-{r}.json'
        dump(feedback, check)
        if cand.exists():
            prev = cand
        entry = row(check, round=r, exit=rc, why=doc.get('why'))
        summary['rows'].append(entry)
        summary['calls'] += int((doc.get('llm') or {}).get('exit') is not None)
        summary['apprentice_tokens'] += tokens(doc.get('llm') or {}, summary['token_missing'], f'A{r}')
        summary['review_tokens'] += tokens((doc.get('review') or {}).get('llm') or {}, summary['token_missing'], f'review{r}')
        if check.get('failed_gate') in (1, 2, 3):
            summary['fails'][str(check['failed_gate'])] += 1
        if check.get('failed_gate') == 1 and FORMAT_RULES.intersection(entry['rules']):
            summary['format_blocks'] += 1
        if rc == 0 and doc.get('ok') is True and passed(check):
            summary['passed'], summary['stop'] = True, 'passed'
            break
        if check.get('failed_gate') is None:
            summary['stop'] = doc.get('error') or doc.get('why') or 'no-confirmed-gate-result'
            break
    summary.update(rounds=len(summary['rows']), reasks=max(0, len(summary['rows'])-1), exit=rc)
    if not summary['stop']:
        summary['stop'] = 'max-rounds'


def group_b(a, out, req, summary):
    rc, _ = execute(['python3', '-B', str(MENU/'examples/aos-tool/build.py'), 'brief', str(req)], out/'brief')
    if rc:
        summary.update(exit=rc, stop='brief-failed')
        return
    env = os.environ.copy()
    env.update(AB_CAPTURE=str(out/'raw'), AOS7_AOS_TOOL_NO_SCOPE='1')
    (out/'raw').mkdir()
    # Leaf review receipt and build result are both captured. Tool definitions otherwise unchanged.
    for kind, target in [('author', AUTHOR), ('gates', P/'packs/author/bin/aos7-gates')]:
        wrapper = out/f'{kind}-capture.py'
        wrapper.write_text('import subprocess,sys\nraise SystemExit(subprocess.call(' + repr(['python3', '-B', str(SELF), '--capture', kind, str(target)]) + '+sys.argv[1:]))\n')
        env['AOS7_AOS_TOOL_' + kind.upper()] = str(wrapper)
    tools = read(MENU/'tools.json')
    argv = tools['tools']['aos-tool-gates']['argv']
    tools['tools']['aos-tool-gates']['argv'] = ['{py}', '-B', str(SELF), '--capture', 'tool', *argv[1:]]
    dump(out/'tools.json', tools)
    env['AOS7_MENU_TOOLS'] = str(out/'tools.json')
    runname = summary['rid']
    directory = Path.cwd()/'menu'/runname
    if directory.exists():
        summary.update(exit=2, stop='run-already-exists')
        return
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'TasksMax=300', 'env',
           'AOS7_AOS_TOOL_NO_SCOPE=1', 'python3', '-B', str(MENU/'bin/aos7-menu'), 'run',
           str(Path.cwd()), str(MENU/'examples/aos-tool/menu.json'), '--run', runname,
           '--var', 'name='+read(req)['name'], '--var', 'request='+str(req),
           '--var', 'review='+('rules' if a.offline else a.review), '--brief', str(out/'brief.stdout')]
    if not a.offline:
        cmd += ['--llm', a.model]
    for attempt in (1, 2):
        rc, _ = execute(cmd, out/f'menu-{attempt}', env)
        if rc != 3:
            break
    state = read(directory/'state.json')
    summary['menu_run'] = str(directory)
    if directory.exists():
        shutil.copytree(directory, out/'menu-evidence', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    logs = state.get('journal', [])
    summary['calls'] = len(state.get('calls', []))
    for call in state.get('calls', []):
        used = call.get('used')
        if used is None:
            summary['token_missing'].append(call.get('call_id'))
        else:
            summary['apprentice_tokens'] += used
    summary['reasks'] = sum(e.get('kind') == 'bad' for e in logs)
    steps = out/'steps'
    steps.mkdir()
    practice = read(MENU/'examples/aos-tool/practice.json').get('replies', []) if a.offline else []
    for k, call in enumerate(state.get('calls', [])):
        if a.offline:
            dump(steps/f'{k+1}.json', dict(call=call, reply=practice[k] if k < len(practice) else None))
        else:
            callid = 'menu-' + hashlib.sha256((state['nonce']+'\n'+call['call_id']).encode()).hexdigest()[:32]
            source = Path.cwd()/'llmcall/llm'/callid
            if source.exists():
                shutil.copytree(source, steps/str(k+1))
    receipts = []
    for path in sorted((out/'raw').glob('author-*.stdout')):
        doc = read(path)
        receipts.append(doc)
        summary['review_tokens'] += tokens((doc.get('review') or {}).get('llm') or {}, summary['token_missing'], path.name)
    leaf_paths = sorted(list((out/'raw').glob('author-*.stdout')) + list((out/'raw').glob('gates-*.stdout')), key=lambda p: int(p.name.split('-')[1]))
    tool_paths = sorted((out/'raw').glob('tool-*.stdout'))
    for n, path in enumerate(tool_paths, 1):
        doc = read(path)
        entry = dict(round=n, gate=doc.get('gate'), rules=[], issues=str(doc.get('issues', ''))[:300],
                     exit=read(path.with_suffix('.meta.json')).get('exit'), raw=str(path))
        begin = int(path.name.split('-')[1])
        end = int(tool_paths[n].name.split('-')[1]) if n < len(tool_paths) else float('inf')
        leaf = next((read(p) for p in leaf_paths if begin < int(p.name.split('-')[1]) < end), {})
        detail = leaf.get('check', leaf)
        entry['rules'] = row(detail)['rules']
        if not entry['rules'] and doc.get('gate') == 1:
            entry['rules'] = re.findall(r'\b(text|json|schema|size|format)\b', str(doc.get('issues', '')))
        summary['rows'].append(entry)
        gate = doc.get('gate')
        if gate in (1,2,3):
            summary['fails'][str(gate)] += 1
    summary['rounds'] = len(summary['rows'])
    summary['format_blocks'] = summary['fails']['1'] + summary['reasks']
    # build validates all three gates before returning ok; menu done alone is insufficient.
    summary['passed'] = rc == 0 and state.get('status') == 'done' and bool(summary['rows']) and read(Path(summary['rows'][-1]['raw'])).get('ok') is True
    summary.update(exit=rc, stop=('passed' if summary['passed'] else 'exit-3-twice' if rc == 3 else state.get('why') or f'menu-exit-{rc}'))
    for e in logs:
        if e.get('kind') in ('bad','exit','stuck'):
            summary['rows'].append(dict(step=e.get('step'), layer=e.get('layer'), kind=e.get('kind'), gate=None,
                                        rules=[], issues=str(e.get('why') or '')[:300]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('group', choices=['A','B'])
    ap.add_argument('task', choices=['gap','runs','audit','mailcount'])
    ap.add_argument('rep', type=int)
    ap.add_argument('outdir')
    ap.add_argument('--model', default='chatgpt-gpt-6-luna')
    ap.add_argument('--review', default='chatgpt-gpt-6-astra-high')
    ap.add_argument('--tag', default='')
    ap.add_argument('--offline', action='store_true')
    a = ap.parse_args()
    out = Path(a.outdir).resolve()
    rid = f'{a.tag}{a.task}{a.group}{a.rep}'
    if not re.fullmatch(r'[A-Za-z0-9_]{1,23}', rid):
        ap.error('rid 必須為 1～23 個英數或底線')
    if (out/'summary.json').exists() or (out/'req').exists():
        print('已跑過或有未完成資料，換 OUTDIR', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(P/f'packs/author/examples/aos-tool-{a.task}', out/'req', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    req = out/'req/request.json'
    doc = read(req)
    doc['rid'] = rid
    dump(req, doc)
    valid = read(out/'req/valid.json')
    valid['rid'] = rid
    dump(out/'valid.json', valid)
    result = dict(group=a.group, task=a.task, rep=a.rep, rid=rid, model=a.model, review=a.review,
                  offline=a.offline, passed=False, rounds=0, calls=0, reasks=0,
                  fails={str(g):0 for g in (1,2,3)}, format_blocks=0, apprentice_tokens=0,
                  review_tokens=0, total_tokens=0, token_missing=[], secs=0, exit=None, stop=None, rows=[])
    start = time.monotonic()
    try:
        (group_a if a.group == 'A' else group_b)(a, out, req, result)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(exit=2, stop=f'driver-error: {exc}')
    result['secs'] = round(time.monotonic()-start, 3)
    result['total_tokens'] = result['apprentice_tokens'] + result['review_tokens']
    dump(out/'summary.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return result['exit'] if result['exit'] is not None else 2


if __name__ == '__main__':
    sys.exit(capture() if sys.argv[1:2] == ['--capture'] else main())
