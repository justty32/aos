"""BRIEF、三關驗證與只新增 apprentice 分支的發布器（標準庫）。"""
import argparse
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import sys

HERE = Path(__file__).resolve().parent


class Unknown(Exception):
    pass


def strict(data):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError('重複鍵：' + k)
            out[k] = v
        return out
    return json.loads(data.decode('utf-8') if isinstance(data, bytes) else data,
                      object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def command(argv, **kw):
    try:
        return subprocess.run(argv, capture_output=True, timeout=900, **kw)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unknown(str(exc)) from exc


def git(ctx, *args, **kw):
    p = command(['git', '-C', str(ctx['repo']), *args], **kw)
    if p.returncode:
        raise Unknown(p.stderr.decode('utf-8', 'replace'))
    return p.stdout


def safe(path):
    return isinstance(path, str) and bool(path) and not path.startswith('/') and '\\' not in path and all(x not in ('', '.', '..') for x in path.split('/')) and not any(ord(c) < 32 for c in path)


def request(path):
    req = strict(path.read_bytes())
    if not isinstance(req, dict) or req.get('kind') not in ('aos-tool', 'aos-module'):
        raise ValueError('需求 kind 不合')
    card = strict((HERE / '../toolcards' / (req['kind'] + '.json')).read_bytes())
    if set(req) != set(card['request_fields']) or type(req['v']) is not int or req['v'] != 1:
        raise ValueError('需求欄位不合')
    for field, pattern in [('rid', r'[A-Za-z0-9_]{1,23}'), ('name', r'[a-z][a-z0-9]{1,15}')]:
        if not isinstance(req[field], str) or not re.fullmatch(pattern, req[field]):
            raise ValueError(field + ' 不合')
    if not all(isinstance(req[k], str) and req[k].strip() for k in ('task', 'goal', 'deliver')):
        raise ValueError('需求文字不合')
    for k in ('work', 'accept'):
        if not isinstance(req[k], list) or not req[k] or not all(isinstance(x, str) and x for x in req[k]):
            raise ValueError(k + ' 不合')
    scope = req['scope']
    if not isinstance(scope, dict) or set(scope) != {'only', 'not', 'max_files'} or type(scope['max_files']) is not int or not 0 < scope['max_files'] <= card['limits']['max_files']:
        raise ValueError('scope 不合')
    if not all(isinstance(scope[k], list) and scope[k] and all(isinstance(x, str) and x for x in scope[k]) for k in ('only', 'not')):
        raise ValueError('範圍須用排除法')
    if not isinstance(req['tools'], list) or not req['tools'] or any(not isinstance(t, dict) or set(t) != {'tool', 'use'} or not all(isinstance(v, str) and v for v in t.values()) for t in req['tools']):
        raise ValueError('tools 不合')
    a = req['answer']
    if not isinstance(a, dict) or set(a) != {'checker', 'fixture'} or not all(safe(x) for x in a.values()):
        raise ValueError('answer 不合')
    return req, card


# 第三關模型審查的退件標準（llmcall 審查與 astra 審查共用）。S3：審查拿需求沒要求的極端邊角退件，佔擋下原因 58%。
REVIEW_CRITERIA = ('只有三種問題能退件（reject）：真錯誤——照需求 work／accept 寫明的行為，在 fixture 這類真實資料上會答錯、'
                   '當掉或退出碼不對；唯讀違規——會建立、刪除或修改輸入（含鎖檔）；越界改動——碰 scope 以外的檔、改 node、'
                   '用了禁用的呼叫。需求沒寫明的極端邊角（例如超長整數字串、西元 1 年或 9999 年附近的時間溢位、落單的 surrogate、'
                   '罕見的換行字元、作業系統特有的格式差異）不是退件理由：verdict 照給 accept，把它們寫進 reasons 當建議，每條以「建議：」開頭。'
                   'reject 時 reasons 每條都要以「錯誤：」「唯讀：」或「越界：」開頭，指明屬於哪一類。')


def brief(req):
    scope = req['scope']
    return '\n'.join([f"# 任務：{req['task']}", '## 背景與唯一目標', req['goal'],
        '## 範圍（排除法寫死）', '只准：' + '、'.join(scope['only']), '不碰：' + '、'.join(scope['not']),
        f"件數 gate：≤{scope['max_files']} 檔", '## 必用工具', '| 工具 | 用途 |', '|---|---|',
        *[f"| `{t['tool']}` | {t['use']} |" for t in req['tools']], '## 工作',
        *[f'{i}. {s}' for i, s in enumerate(req['work'], 1)], '## 交付', req['deliver'],
        f"## 驗收（固定 {len(req['accept'])} 條，做完就停）",
        *[f'{i}. {s}' for i, s in enumerate(req['accept'], 1)]])


def result(issues):
    return {'ok': not issues, 'issues': issues}


def insert_row(text, row, prefix):
    """在最後一個相符表格內插列；沒有相符列才附加檔尾。"""
    lines = text.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix.split('{name}', 1)[0])]
    end = len(lines)
    if matches:
        end = matches[-1] + 1
        while end < len(lines) and lines[end].startswith('|'):
            end += 1
    before = ''.join(lines[:end])
    return before + ('' if not before or before.endswith('\n') else '\n') + row + '\n' + ''.join(lines[end:])


def materialize(ctx):
    if 'top' in ctx:
        return
    blob = git(ctx, 'archive', ctx['ref'], ctx['prefix'])
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        archive.extractall(ctx['tmp'], filter='data')
    top = ctx['top'] = Path(ctx['tmp']) / ctx['prefix']
    for path, content in ctx['candidate'].get('files', {}).items():
        if safe(path) and isinstance(content, str):
            dest = top / path
            if not dest.resolve().is_relative_to(top.resolve()):
                raise ValueError('候選寫入穿越 symlink')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding='utf-8')
            if path == ctx['entry']:
                dest.chmod(0o755)
    rowfile = top / ctx['card']['row']['file']
    if not rowfile.resolve().is_relative_to(top.resolve()):
        raise ValueError('row 穿越 symlink')
    text = rowfile.read_bytes().decode('utf-8')
    rowfile.write_bytes(insert_row(text, ctx['candidate'].get('row', ''), ctx['card']['row']['prefix']).encode('utf-8'))


def gate_static(ctx):
    c, card, req = ctx['candidate'], ctx['card'], ctx['request']
    issues = []
    def add(rule, why):
        issues.append({'rule': rule, 'why': why})
    if not isinstance(c, dict):
        return result([{'rule': 'schema', 'why': '候選須為物件'}])
    files = c.get('files', {})
    if set(c) != {'v', 'rid', 'kind', 'name', 'files', 'row', 'report'} or type(c.get('v')) is not int or c.get('v') != 1 or any(c.get(k) != req[k] for k in ('rid', 'kind', 'name')) or not isinstance(files, dict) or not all(isinstance(v, str) for v in files.values()) or not isinstance(c.get('row'), str) or not isinstance(c.get('report'), str) or '以後交接書該點名的工具' not in c.get('report', ''):
        add('schema', '候選欄位、識別或 REPORT 不合')
        return result(issues)
    root = ctx['root']
    paths = git(ctx, 'ls-tree', '-r', '--name-only', ctx['ref']).decode().splitlines()
    if git(ctx, 'ls-tree', ctx['ref'], '--', ctx['prefix'] + '/' + root).strip():
        add('territory', 'ref 已有 root，只准新增包')
    for p in files:
        if not safe(p) or not p.startswith(root + '/'):
            add('territory', p)
    row = c['row']
    if '\n' in row or '\r' in row or not row.startswith(card['row']['prefix'].format(name=req['name'])) or not row.endswith('|'):
        add('territory', 'row 必須為指定前綴的一列')
    if any(root + '/' + p.format(name=req['name']) not in files for p in card['required']) or len(files.get(ctx['entry'], '').splitlines()) > card['entry_max_lines']:
        add('layout', '缺必要檔或入口太長')
    tests = [p for p in files if re.fullmatch(re.escape(root) + r'/tests/test_[^/]+\.py', p)]
    if not tests or any(Path(p).name in {Path(x).name for x in paths if Path(x).match('test_*.py')} for p in tests):
        add('tests', '缺測試或測試檔名撞名')
    # 超標要講清楚哪個檔、實際多大、上限多少，學徒才改得對（S3：只說「超標」時筆記只學到「要精簡」）。
    lim, max_files = card['limits'], min(card['limits']['max_files'], req['scope']['max_files'])
    if len(files) > max_files:
        add('size', f'檔數 {len(files)} 超過上限 {max_files}')
    if len(ctx['bytes']) > lim['max_candidate_bytes']:
        add('size', f"整份候選 {len(ctx['bytes'])} bytes 超過上限 {lim['max_candidate_bytes']} bytes")
    for p, s in sorted(files.items()):
        n = len(s.encode('utf-8'))
        if n > lim['max_file_bytes']:
            add('size', f"{p} 有 {n} bytes，超過每檔上限 {lim['max_file_bytes']} bytes（可拆成多個檔，檔數上限 {max_files}）")
    readme = re.sub(r'^\s*(```|~~~)[^\n]*\n.*?^\s*\1[^\n]*(?:\n|$)', '', files.get(root + '/README.md', ''), flags=re.M | re.S)
    if any(not re.search(r'^(?:- )?' + re.escape(s), readme, re.M) for s in card['readme_must']):
        add('readme', 'README 缺指定章節')
    materialize(ctx)
    lint = ctx['source_repo'] / 'wf/tools/wf-lint.sh'
    if not lint.is_file():
        raise Unknown('wf-lint 不在')
    p = command(['bash', str(lint), '--quiet', str(ctx['top'] / root)])
    for line in p.stdout.decode('utf-8', 'replace').splitlines():
        if line.startswith('BROKEN'):
            add('lint', line)
    for link in re.findall(r'\]\(([^)]+)\)', row):
        target = link.split('#')[0]
        if target and not re.match(r'[a-z]+:', target) and not (ctx['top'] / card['row']['file']).parent.joinpath(target).exists():
            add('lint', 'row 壞連結：' + link)
    return result(issues)


def jail(ctx, argv):
    """白名單檔案系統、空環境與 HOME；只有物化 tmp 可寫。"""
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise Unknown('bwrap 不在：第二關要在沙箱跑學徒的碼')
    tmp = str(ctx['tmp'])
    mounts = [bwrap, '--unshare-all', '--die-with-parent', '--new-session', '--clearenv',
              '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/tmp/home',
              '--setenv', 'LANG', 'C.UTF-8', '--ro-bind', '/usr', '/usr']
    for name in ('/bin', '/lib', '/lib64', '/sbin'):
        path = Path(name)
        if path.is_symlink():
            mounts += ['--symlink', os.readlink(path), name]
        elif path.is_dir():
            mounts += ['--ro-bind', name, name]
    argv = [*mounts, '--ro-bind', '/etc', '/etc', '--proc', '/proc', '--dev', '/dev',
            '--tmpfs', '/tmp', '--dir', '/tmp/home', '--bind', tmp, tmp, '--', *argv]
    if not ctx['no_scope']:
        argv = ['systemd-run', '--user', '--scope', '-q', '-p', 'TasksMax=300', '-p', 'RuntimeMaxSec=900', *argv]
    return argv


def gate_tests(ctx):
    materialize(ctx)
    top = ctx['top']
    reqdir = Path(ctx['tmp']) / 'req'
    p = command(jail(ctx, ['python3', str(top / 'tests/run_all.py'), ctx['root'] + '/tests']), cwd=top)
    issues = []
    output = (p.stdout + p.stderr).decode('utf-8', 'replace')
    count = re.search(r'Ran (\d+) tests?\b', output)
    if not count or int(count[1]) == 0:
        issues.append({'rule': 'test', 'why': '沒有實際測試'})
    elif p.returncode:
        issues.append({'rule': 'test', 'why': '\n'.join((p.stdout + p.stderr).decode('utf-8', 'replace').splitlines()[-20:])})
    a = ctx['request']['answer']
    shutil.copytree(ctx['reqdir'], reqdir)
    p = command(jail(ctx, ['python3', str(reqdir / a['checker']), str(top), str(reqdir / a['fixture'])]), cwd=top)
    try:
        answer = strict(p.stdout)
    except (ValueError, UnicodeError):
        answer = {'ok': False, 'issues': [p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')]}
    if p.returncode or not isinstance(answer, dict) or answer.get('ok') is not True:
        issues.append({'rule': 'answer', 'why': answer.get('issues', []) if isinstance(answer, dict) else answer})
    return result(issues)


def gate_review(ctx):
    reviewer = ctx['reviewer']
    issues = []
    if reviewer == 'rules':
        for path, content in ctx['candidate']['files'].items():
            if not path.endswith(('.md', '.json')):
                for rule in ctx['card']['review_rules']:
                    for m in re.finditer(rule['re'], content, re.M):
                        issues.append({'rule': 'review', 'why': f"{rule['why']}：{path}:{content[:m.start()].count(chr(10))+1}"})
        return result(issues)
    if reviewer.startswith('file:'):
        text = Path(reviewer[5:]).read_text(encoding='utf-8')
    else:
        materialize(ctx)
        # 回覆檔放沙箱碰不到的另一個暫存夾，學徒的碼不能預埋審查結果。
        side = tempfile.TemporaryDirectory(prefix='aos-review-')
        out = Path(side.name) / 'review.json'
        prompt = brief(ctx['request']) + '\n' + json.dumps(ctx['candidate'], ensure_ascii=False) + '\n①②：' + json.dumps(ctx['gates'], ensure_ascii=False) + '\n①② 已由檢查器在沙箱跑過、結果如上；你只讀碼，不要執行或重跑。審查所有檔案與需求。' + REVIEW_CRITERIA + '只回 {"verdict":"accept"|"reject","reasons":[…]}'
        p = command(['codex', 'exec', '-m', 'gpt-6-astra', '-c', 'model_reasoning_effort="high"', '-s', 'read-only', '--skip-git-repo-check', '-C', ctx['tmp'], '-o', str(out), '-'], input=prompt.encode())
        if p.returncode or not out.exists():
            raise Unknown('審查器當掉：' + p.stderr.decode('utf-8', 'replace')[-2000:])
        text = out.read_text(encoding='utf-8')
        side.cleanup()
    text = text.strip()
    fence = re.fullmatch(r'```json\s*\n(.*?)\n```', text, re.S)
    if fence:
        text = fence[1]
    try:
        verdict = strict(text)
        if not isinstance(verdict, dict) or set(verdict) != {'verdict', 'reasons'} or verdict['verdict'] not in ('accept', 'reject') or not isinstance(verdict['reasons'], list) or not all(isinstance(x, str) for x in verdict['reasons']):
            raise ValueError('schema')
    except (ValueError, TypeError):
        return result([{'rule': 'review', 'why': '審查回覆格式不合'}])
    # reject 卻只列「建議：」＝沒有能退件的理由，照 accept 算（極端邊角只當建議，不擋）。
    if verdict['verdict'] != 'accept' and not (verdict['reasons'] and all(x.lstrip().startswith('建議：') for x in verdict['reasons'])):
        issues.append({'rule': 'review', 'why': verdict['reasons']})
    return result(issues)


GATES = {1: gate_static, 2: gate_tests, 3: gate_review}


def run_gates(ctx):
    r = ctx['request']
    sha = hashlib.sha256(ctx['bytes']).hexdigest()
    out = {'ok': False, 'rid': r['rid'], 'name': r['name'], 'job': r['rid'] + '_' + sha[:8], 'candidate_sha': sha, 'failed_gate': None, 'gates': {str(n): {'ok': None} for n in GATES}}
    ctx['gates'] = out['gates']
    ctx['out'] = out
    for n, fn in GATES.items():
        out['failed_gate'] = n
        out['gates'][str(n)] = fn(ctx)
        if not out['gates'][str(n)]['ok']:
            out['failed_gate'] = n
            return out
    out['ok'] = True
    out['failed_gate'] = None
    return out


def publish(ctx, out):
    env = dict(os.environ, GIT_INDEX_FILE=str(Path(ctx['tmp']) / 'git-index'), GIT_AUTHOR_NAME='aos-apprentice', GIT_AUTHOR_EMAIL='apprentice@aos.local', GIT_COMMITTER_NAME='aos-apprentice', GIT_COMMITTER_EMAIL='apprentice@aos.local')
    parent = git(ctx, 'rev-parse', ctx['ref'] + '^{commit}').decode().strip()
    git(ctx, 'read-tree', parent, env=env)
    contents = {p: s.encode('utf-8') for p, s in ctx['candidate']['files'].items()}
    rowfile = ctx['card']['row']['file']
    original = git(ctx, 'show', parent + ':' + ctx['prefix'] + '/' + rowfile)
    contents[rowfile] = insert_row(original.decode('utf-8'), ctx['candidate']['row'], ctx['card']['row']['prefix']).encode('utf-8')
    for path, data in contents.items():
        oid = git(ctx, 'hash-object', '-w', '--stdin', input=data).decode().strip()
        mode = '100755' if path == ctx['entry'] else '100644'
        git(ctx, 'update-index', '--add', '--cacheinfo', mode, oid, ctx['prefix'] + '/' + path, env=env)
    tree = git(ctx, 'write-tree', env=env).decode().strip()
    branch = 'apprentice/' + out['job']
    ref = 'refs/heads/' + branch
    out.update(branch=branch, commit=None, dup=False)
    if command(['git', '-C', str(ctx['repo']), 'symbolic-ref', '-q', ref]).returncode == 0:
        out['ok'] = False
        return 1
    old = command(['git', '-C', str(ctx['repo']), 'rev-parse', '--verify', ref])
    if old.returncode == 0:
        out['commit'] = old.stdout.decode().strip()
        out['dup'] = git(ctx, 'rev-parse', ref + '^{tree}').decode().strip() == tree
        out['ok'] = out['dup']
        return 0 if out['dup'] else 1
    msg = f"apprentice {ctx['request']['rid']}: {ctx['request']['task']}\n\n{ctx['candidate']['report']}\n\ncandidate_sha: {out['candidate_sha']}\n"
    commit = git(ctx, 'commit-tree', tree, '-p', parent, input=msg.encode(), env=env).decode().strip()
    p = command(['git', '-C', str(ctx['repo']), 'update-ref', '--no-deref', ref, commit, '0' * len(commit)])
    if p.returncode:
        # 競爭者可能已新建；重讀，按樹判 dup/conflict。
        if command(['git', '-C', str(ctx['repo']), 'rev-parse', '--verify', ref]).returncode:
            raise Unknown(p.stderr.decode('utf-8', 'replace'))
        return publish(ctx, out)
    out['commit'] = commit
    return 0


def one_line(value, limit=180):
    text = ' '.join(str(value).split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'aos7-gates: ' + one_line(message) + '。給需求與候選檔，例如 aos7-gates check request.json candidate.json；用法看 aos7-gates --help\n')

    def format_help(self):
        return ('aos7-gates：驗候選，過三關才發布\n'
                '  brief request.json  印任務說明\n'
                '  check request.json candidate.json  離線驗三關\n'
                '  publish request.json candidate.json --repo REPO  建分支\n'
                '  --ref REF  指定基準（預設 HEAD）\n'
                '  --reviewer rules|astra|file:PATH  預設 rules\n'
                '其他選項見 ../ADVANCED.md\n')


def error_line(out, code):
    if code == 3:
        evidence = '分支可能已建，分支與候選證據留著' if out.get('branch') else '候選證據留著，沒建分支'
        return 'aos7-gates: 不確定：' + one_line(out.get('unknown') or '檢查未跑完') + '。' + evidence + '；照原樣再跑一次'
    if code == 1 and out.get('branch') and out.get('failed_gate') is None:
        return 'aos7-gates: 分支 ' + out['branch'] + ' 已存在且內容不同或是 symbolic ref。換候選或由人刪舊分支'
    n = out.get('failed_gate') or 1
    issue = (out.get('gates', {}).get(str(n), {}).get('issues') or [{}])[0]
    if code == 1:
        return f"aos7-gates: 第 {n} 關沒過（{issue.get('rule')}：{one_line(issue.get('why', ''), 80)}）。照 stdout JSON 的 gates 修正候選再跑"
    return 'aos7-gates: ' + one_line(issue.get('why') or '輸入不合') + '。給需求與候選檔，例如 aos7-gates check request.json candidate.json'


def main(argv=None):
    ap = ArgumentParser(prog='aos7-gates')
    ap.add_argument('cmd', choices=['brief', 'check', 'publish'])
    ap.add_argument('request', type=Path)
    ap.add_argument('candidate', nargs='?', type=Path)
    ap.add_argument('--reviewer', default='rules')
    ap.add_argument('--no-scope', action='store_true')
    ap.add_argument('--repo', type=Path)
    ap.add_argument('--ref', default='HEAD')
    a = ap.parse_args(argv)
    out = {'ok': False, 'failed_gate': 1, 'gates': {'1': {'ok': False, 'issues': []}, '2': {'ok': None}, '3': {'ok': None}}}
    ctx = {}
    try:
        req, card = request(a.request)
        if a.cmd == 'brief':
            print(brief(req))
            return 0
        if a.candidate is None or not (a.reviewer in ('rules', 'astra') or a.reviewer.startswith('file:')):
            raise ValueError('候選或 reviewer 不合')
        data = a.candidate.read_bytes()
        out.update(rid=req['rid'], name=req['name'], candidate_sha=hashlib.sha256(data).hexdigest(), job=req['rid'] + '_' + hashlib.sha256(data).hexdigest()[:8])
        candidate = strict(data)
        source = command(['git', '-C', str(HERE), 'rev-parse', '--show-toplevel'])
        if source.returncode:
            raise Unknown('git toplevel 不在')
        repo = Path(source.stdout.decode().strip())
        if a.cmd == 'publish' and a.repo is None:
            message = f"publish 要用 --repo 指定分支建在哪個 git repo，沒給就不建。練習請建在臨時 clone（照 checkers/README.md）；要建在這個 repo 就加 --repo {repo}（分支 apprentice/{out['job']}）"
            out['gates']['1'] = result([{'rule': 'repo', 'why': message}])
            print(json.dumps(out, ensure_ascii=False))
            print('aos7-gates: ' + message, file=sys.stderr)
            return 2
        prefix = HERE.parents[2].relative_to(repo).as_posix()
        with tempfile.TemporaryDirectory(prefix='aos-three-') as tmp:
            ctx = dict(source_repo=repo, request=req, card=card, candidate=candidate, bytes=data, repo=(a.repo or repo).resolve(), prefix=prefix, ref=a.ref, tmp=tmp, reqdir=a.request.resolve().parent, reviewer=a.reviewer, no_scope=a.no_scope, root=card['root'].format(name=req['name']))
            ctx['ref'] = git(ctx, 'rev-parse', ctx['ref'] + '^{commit}').decode().strip()
            ctx['entry'] = ctx['root'] + '/' + card['entry'].format(name=req['name'])
            out = run_gates(ctx)
            code = publish(ctx, out) if out['ok'] and a.cmd == 'publish' else (0 if out['ok'] else 1)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.EISDIR):
            out['ok'] = False
            out['gates']['1'] = result([{'rule': 'schema', 'why': str(exc)}])
            code = 2
        else:
            out = ctx.get('out', out)
            out.update(ok=False, unknown=str(exc))
            code = 3
    except Unknown as exc:
        out = ctx.get('out', out)
        out.update(ok=False, unknown=str(exc))
        code = 3
    except (ValueError, UnicodeError, OSError, TypeError, KeyError, tarfile.TarError) as exc:
        out['ok'] = False
        out['gates']['1'] = result([{'rule': 'json' if isinstance(exc, (ValueError, UnicodeError)) else 'schema', 'why': str(exc)}])
        code = 2
    print(json.dumps(out, ensure_ascii=False))
    if code:
        print(error_line(out, code), file=sys.stderr)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
