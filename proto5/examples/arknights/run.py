#!/usr/bin/env python3
"""arknights 強模型版試跑（2026-09-25 第 2 段）：開機、建隊、丟一句話、等單子結束、存紀錄。

用法（從哪裡跑都行）：
  python3 run.py one 老何塞                  # 門房規則「補人物 X」直接開單給 writer-1
  python3 run.py batch 老木頭 老薑 老財       # 「補一批人物：…」落穿給領隊，領隊拆三張單
  python3 run.py stop                        # 停團隊、停機

每次都：aos down → 設 AOS_HOPS 重開機 → 專案副本 git reset --hard 到基線、清掉 lore/ 裡沒追蹤的檔 → 刪掉團隊資料夾重建
→ aos-team ask → 每 5 秒看一次單子，頂層單全部 done／failed／cancelled 或逾時就停 → 紀錄寫進 <專案>/aos-runs/<時間>/。
等人回答的題目（ask_human）不自動回：印出來，你用 aos-team answer 回（環境變數照 env.sh）。

可改的設定（環境變數）：
  ARK_PROJECT   專案副本（預設 ~/tmp/arknights-try；換成本尊要改 team.json 的 project，見 README）
  ARK_BASE      副本的基線 commit（預設 aos-try 分支上「aos 試跑基線」那個 commit，找不到就用 HEAD）
  ARK_AOS       開機資料夾（daemon、kernel、團隊都放這；預設 ~/tmp/arknights-aos）
  ARK_TIMEOUT   等多久（秒；預設 one 2400、batch 3600）
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

EX = Path(__file__).resolve().parent
PROTO = EX.parent.parent
CLI = PROTO / 'cli'
PROJECT = Path(os.path.expanduser(os.environ.get('ARK_PROJECT', '~/tmp/arknights-try')))
H = Path(os.path.expanduser(os.environ.get('ARK_AOS', '~/tmp/arknights-aos')))
TEAM = H / 'team'


def env(hops=None):
    e = dict(os.environ, PATH='%s:%s' % (CLI, os.environ['PATH']), AOS_DAEMON_HOME=str(H / 'D'),
             AOS_KERNEL_HOME=str(H / 'K'), PYTHONDONTWRITEBYTECODE='1', AOS_TEAM_HOME=str(TEAM))
    e.pop('AOS_HOPS', None)
    if hops:
        e['AOS_HOPS'] = str(hops)
    return e


def sh(argv, check=True, timeout=300, hops=None):
    r = subprocess.run([str(a) for a in argv], env=env(hops), capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise SystemExit('失敗：%s\n%s%s' % (' '.join(map(str, argv)), r.stdout, r.stderr))
    return r


def team(*argv, **kw):
    return sh([CLI / 'aos-team', *argv, '--target', TEAM], **kw)


def git(*argv, check=True):
    return sh(['git', '-C', PROJECT, *argv], check=check)


def base_commit():
    if os.environ.get('ARK_BASE'):
        return os.environ['ARK_BASE']
    r = git('log', '--format=%H', '--grep', 'aos 試跑基線', '-1', check=False)
    return r.stdout.strip() or 'HEAD'


def write_configs():
    """llm.json、kernel.json、env.sh、展開好的 team.json 寫進 H。"""
    H.mkdir(parents=True, exist_ok=True)
    shutil.copy(EX / 'llm.json', H / 'llm.json')
    kernel = {"pools": {"default": {"count": 5},
                        "llm": {"count": 4, "envs": {"AOS_LLM_CONFIG": str(H / 'llm.json')}}}}
    (H / 'kernel.json').write_text(json.dumps(kernel, ensure_ascii=False, indent=1), encoding='utf-8')
    (H / 'env.sh').write_text(
        'export PATH=%s:$PATH\nexport AOS_DAEMON_HOME=%s AOS_KERNEL_HOME=%s AOS_TEAM_HOME=%s\nexport PYTHONDONTWRITEBYTECODE=1\n'
        % (CLI, H / 'D', H / 'K', TEAM), encoding='utf-8')
    roster = json.loads((EX / 'team.json').read_text(encoding='utf-8'))
    roster['project'] = os.path.expanduser(roster['project'])
    for m in roster['members'].values():
        if m['template'].startswith('./'):            # 自訂模板一律寫成絕對路徑（相對路徑是照 cwd 解的，郵差會找不到）
            m['template'] = str(EX / m['template'][2:])
        for k, v in list(m.get('mounts', {}).items()):
            if isinstance(v, dict):
                v['$val'] = os.path.expanduser(v['$val'])
            else:
                m['mounts'][k] = os.path.expanduser(v)
    (H / 'team.json').write_text(json.dumps(roster, ensure_ascii=False, indent=2), encoding='utf-8')


def boot(hops):
    sh([CLI / 'aos', 'down'], check=False, timeout=120)
    if not (H / 'K').exists():
        sh([CLI / 'aos-kernel', 'init', '--config', H / 'kernel.json'])
    sh([CLI / 'aos', 'up'], hops=hops, timeout=120)


def reset_project():
    git('reset', '-q', '--hard', base_commit())
    git('clean', '-q', '-fd', '--', 'lore')


def build_team():
    if TEAM.exists():
        team('stop', check=False)
        shutil.rmtree(TEAM)
    team('init', '--config', H / 'team.json')
    team('route', 'save', EX / 'routes.json')
    team('start')


def poll(expect, timeout):
    t0 = time.time()
    seen_q, status, top = set(), 'timeout', []
    while time.time() - t0 < timeout:
        time.sleep(5)
        for q in json.loads(team('wait', 'ls', '--json').stdout or '[]'):
            if q['id'] not in seen_q:
                seen_q.add(q['id'])
                print('[等人回答] %s %s' % (q['id'], q.get('question', '')[:300]), flush=True)
        tickets = json.loads(team('task', 'ls', '--all', '--json').stdout or '[]')
        top = [t for t in tickets if not t.get('parent')]
        line = ' '.join('%s:%s/%s' % (t['id'], t['status'], t.get('attempt')) for t in tickets)
        print('%4ds %s' % (time.time() - t0, line), flush=True)
        if len(top) >= expect and all(t['status'] in ('done', 'failed', 'cancelled') for t in top):
            status = 'done' if all(t['status'] == 'done' for t in top) else 'failed'
            break
    return status, time.time() - t0, sorted(seen_q)


def save(out_dir, meta, hops):
    out_dir.mkdir(parents=True, exist_ok=True)
    tickets = json.loads(team('task', 'ls', '--all', '--json', check=False).stdout or '[]')
    (out_dir / 'tasks.json').write_text(json.dumps(tickets, ensure_ascii=False, indent=1), encoding='utf-8')
    shows = []
    for t in tickets:
        shows.append(team('task', 'show', t['id'], check=False).stdout)
    (out_dir / 'tasks.txt').write_text('\n\n'.join(shows), encoding='utf-8')
    for t in tickets:
        src = TEAM / 'team' / 'tasks' / ('%s.json' % t['id'])
        if src.is_file():
            (out_dir / 'tasks').mkdir(exist_ok=True)
            shutil.copy(src, out_dir / 'tasks' / src.name)
    score = team('score', '--json', check=False).stdout
    (out_dir / 'score.json').write_text(score, encoding='utf-8')
    (out_dir / 'score.txt').write_text(team('score', check=False).stdout, encoding='utf-8')
    per_task = {}
    for t in tickets:
        if not t.get('parent'):
            r = team('score', '--task', t['id'], '--json', check=False)
            try:
                per_task[t['id']] = json.loads(r.stdout)
            except ValueError:
                per_task[t['id']] = {'error': r.stderr}
    (out_dir / 'score-per-task.json').write_text(json.dumps(per_task, ensure_ascii=False, indent=1), encoding='utf-8')
    (out_dir / 'mail.txt').write_text(team('mail', '--full', check=False).stdout, encoding='utf-8')
    route_log = TEAM / 'team' / 'route.log'
    if route_log.is_file():
        shutil.copy(route_log, out_dir / 'route.log')
    if hops.is_file():
        rep = sh(['python3', PROTO / 'lib' / 'aos_hops.py', 'report', hops], check=False)
        (out_dir / 'hops-report.txt').write_text(rep.stdout + rep.stderr, encoding='utf-8')
        rep = sh(['python3', PROTO / 'lib' / 'aos_hops.py', 'report', hops, '--json'], check=False)
        (out_dir / 'hops-report.json').write_text(rep.stdout, encoding='utf-8')
    diff = git('status', '--short', '--untracked-files=all', '--', 'lore', check=False).stdout
    (out_dir / 'project-status.txt').write_text(diff, encoding='utf-8')
    (out_dir / 'project.diff').write_text(git('diff', '--', 'lore', check=False).stdout, encoding='utf-8')
    # 交件快照：這次寫出來的 lore 檔原樣留一份（下一次試跑會把專案退回基線）
    snap = out_dir / 'lore-after'
    for line in diff.splitlines():
        rel = line[3:].strip().strip('"')
        src = PROJECT / rel
        if src.is_file():
            (snap / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, snap / rel)
    for member in sorted((TEAM / 'members').iterdir()):
        logs = member / 'log'
        if logs.is_dir():
            dst = out_dir / 'members' / member.name
            shutil.copytree(logs, dst / 'log', dirs_exist_ok=True)
    try:
        s = json.loads(score)
    except ValueError:
        s = {}
    meta.update({'tickets': [{'id': t['id'], 'assignee': t.get('assignee'), 'status': t['status'],
                              'attempt': t.get('attempt'), 'parent': t.get('parent')} for t in tickets],
                 'score_summary': {k: s.get(k) for k in ('summary', 'calls', 'tokens', 'seconds') if k in s}})
    (out_dir / 'result.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: meta[k] for k in ('mode', 'names', 'status', 'wall_s', 'tickets')}, ensure_ascii=False))


def main(argv):
    if not argv or argv[0] not in ('one', 'batch', 'stop'):
        print(__doc__)
        return 2
    if argv[0] == 'stop':
        if TEAM.exists():
            team('stop', check=False)
        sh([CLI / 'aos', 'down'], check=False)
        return 0
    mode, names = argv[0], argv[1:]
    if not names or (mode == 'one' and len(names) != 1):
        print(__doc__)
        return 2
    stamp = time.strftime('%Y%m%d-%H%M%S')
    out_dir = PROJECT / 'aos-runs' / ('%s-%s' % (stamp, mode))
    out_dir.mkdir(parents=True)
    hops = out_dir / 'hops.jsonl'
    write_configs()
    if TEAM.exists():
        team('stop', check=False)
    boot(hops)
    reset_project()
    build_team()
    sentence = ('補人物 %s' % names[0]) if mode == 'one' else ('補一批人物：%s' % '、'.join(names))
    timeout = int(os.environ.get('ARK_TIMEOUT', 2400 if mode == 'one' else 3600))
    t0 = time.time()
    print(team('ask', sentence).stdout.strip(), flush=True)
    status, wall, questions = poll(1 if mode == 'one' else len(names), timeout)
    meta = {'mode': mode, 'names': names, 'sentence': sentence, 'status': status, 'wall_s': round(wall, 1),
            'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(t0)), 'questions': questions,
            'base_commit': base_commit(), 'model': 'gpt-6-astra（LiteLLM chatgpt-gpt-6-astra，預設檔位）'}
    team('stop', check=False)
    save(out_dir, meta, hops)
    print('紀錄：%s' % out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
