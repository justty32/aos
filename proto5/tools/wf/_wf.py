"""wf 工具包共用：快照位置、殘留計數、跑快照的 wf-lint、staging 版的 wf-init、tabledb。

給別隊當 Python 用（T2 驗收員）：
    import sys; sys.path.insert(0, '<proto5>/tools/wf'); import _wf
    _wf.residue(project_dir)            -> {'total', 'counts', 'hits', 'unreadable'}
    _wf.lint(project_dir, strict=True)  -> {'status': pass|fail|error, 'exit', 'ok', 'total_line', 'summaries',
                                            'problems', 'output'}
兩個都不寫專案（lint 只在給了 log_path 時寫那一個檔）、不叫模型、只跑本包自帶的快照程式。
"""
import json
import os
import re
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snapshot')
MARKERS = ('{{', '〔導入判斷〕', '〔模板說明〕')
SKIP_DIRS = ('.git',)
STAGING = '.wf-staging-'
BACKUP = '.wf-backup-'
COMMIT = 'commit.json'
LINT_TIMEOUT = 150
INIT_TIMEOUT = 150
PROBLEM = re.compile(r'^(BROKEN|OVERSIZE|BIGLIST|RESIDUE|QUERYCMD|INBOX|WARN|FATAL|wf-init failed)')


class WfError(Exception):
    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


# 會改變快照程式行為的環境變數：Python 搜尋路徑／啟動檔、bash 非互動啟動檔
DROP_ENV = ('PYTHONPATH', 'PYTHONSTARTUP', 'PYTHONHOME', 'PYTHONINSPECT', 'PYTHONUSERBASE', 'PYTHONSAFEPATH',
            'BASH_ENV', 'ENV', 'CDPATH', 'GLOBIGNORE', 'SHELLOPTS', 'BASHOPTS')


def _env():
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV and not k.startswith('BASH_FUNC_')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'   # 快照是唯讀的（關牢時也是），不要寫 __pycache__
    env['PYTHONNOUSERSITE'] = '1'          # 不讀使用者的 site-packages
    return env


def _skip_dir(name):
    return name in SKIP_DIRS or name.startswith(STAGING) or name.startswith(BACKUP)


# ---------------------------------------------------------------- 殘留 ----

def residue(project_dir):
    """照 IMPORT.md 的 grep：專案裡所有 .md 的三種殘留。counts＝出現次數（跟 wf-lint 同算法）；
    hits＝[(相對路徑, 行號, 記號)]（一行有幾種就幾筆）；unreadable＝[(相對路徑, 原因)]，不當成 0。
    不跟符號連結（跟 grep -r 一樣），連結到的 .md 列進 unreadable。"""
    project_dir = os.path.realpath(project_dir)
    counts = dict.fromkeys(MARKERS, 0)
    hits, unreadable = [], []

    def onerror(e):
        unreadable.append((os.path.relpath(e.filename, project_dir) if e.filename else '?',
                           e.strerror or str(e)))

    for dp, dns, fns in os.walk(project_dir, onerror=onerror):
        dns[:] = sorted(d for d in dns if not _skip_dir(d))
        for fn in sorted(fns):
            if not fn.endswith('.md'):
                continue
            full = os.path.join(dp, fn)
            relp = os.path.relpath(full, project_dir)
            if os.path.islink(full):
                unreadable.append((relp, 'symbolic link (not followed)'))
                continue
            try:
                with open(full, encoding='utf-8', errors='replace') as f:
                    lines = f.read().split('\n')
            except OSError as e:
                unreadable.append((relp, e.strerror or str(e)))
                continue
            for i, line in enumerate(lines, 1):
                for m in MARKERS:
                    n = line.count(m)
                    if n:
                        counts[m] += n
                        hits.append((relp, i, m))
    return {'total': sum(counts.values()), 'counts': counts, 'hits': hits, 'unreadable': unreadable}


def residue_text(res, limit=200):
    c = res['counts']
    head = 'residue total=%d ({{=%d 導入判斷=%d 模板說明=%d) unreadable=%d' % (
        res['total'], c['{{'], c['〔導入判斷〕'], c['〔模板說明〕'], len(res['unreadable']))
    out = [head]
    for relp, line, m in res['hits'][:limit]:
        out.append('%s:%d %s' % (relp, line, m))
    if len(res['hits']) > limit:
        out.append('... %d more lines not shown' % (len(res['hits']) - limit))
    for relp, why in res['unreadable']:
        out.append('UNREADABLE %s: %s' % (relp, why))
    return '\n'.join(out)


# ---------------------------------------------------------------- lint ----

def lint(project_dir, strict=True, log_path=None, timeout=LINT_TIMEOUT):
    """跑快照裡的 wf-lint.sh（不跑專案裡那份）。回 {'status', 'exit', 'ok', 'total_line', 'summaries',
    'problems', 'output'}；status＝pass／fail（檢查有效）／error（檢查器本身故障，不能當成通過或不通過）。
    逾時、叫不起 bash 才 raise WfError。"""
    # 用 '.'＋cwd＝專案：輸出裡的路徑都是相對專案的短路徑
    argv = ['bash', os.path.join(SNAP, 'tools', 'wf-lint.sh')] + (['--strict'] if strict else []) + ['.']
    try:
        p = subprocess.run(argv, cwd=project_dir, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        raise WfError('Timeout', 'wf-lint did not finish in %d s' % timeout)
    except OSError as e:
        raise WfError('SpawnFailed', 'cannot run bash: %s' % (e.strerror or e))
    output = p.stdout.decode('utf-8', 'replace')
    if log_path:
        tmp = '%s.%d.tmp' % (log_path, os.getpid())
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(output)
        os.replace(tmp, log_path)
    lines = output.splitlines()
    total = next((ln for ln in reversed(lines) if ln.startswith('TOTAL ')), '')
    problems = [ln for ln in lines if PROBLEM.match(ln)]
    summaries = [ln for ln in lines if ln.startswith('SUMMARY ')]
    if p.returncode in (0, 1) and total:
        status = 'pass' if p.returncode == 0 else 'fail'
    else:                   # 檢查器自己壞了：退出碼不是 0/1，或沒印 TOTAL（被砍、FATAL、快照缺檔）
        status = 'error'
    return {'status': status, 'exit': p.returncode, 'ok': status == 'pass', 'total_line': total,
            'summaries': summaries, 'problems': problems, 'output': output}


# ---------------------------------------------------------------- init ----

def flavors():
    d = os.path.join(SNAP, 'flavors')
    return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))


def _hook(phase):
    """只給測試：AOS_WF_TEST_PAUSE=<phase> 時寫 AOS_WF_TEST_MARK 標記檔後睡住，讓測試在窗口裡 KILL。"""
    if os.environ.get('AOS_WF_TEST_PAUSE') == phase:
        mark = os.environ.get('AOS_WF_TEST_MARK')
        if mark:
            with open(mark, 'w') as f:
                f.write(phase)
        time.sleep(60)


def _write_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _manifest(tree):
    """staging 樹裡的檔（含符號連結）與空資料夾；AGENTS.md 永遠排最後（它在＝導入完成）。"""
    files, dirs = [], []
    for dp, dns, fns in os.walk(tree):
        dns.sort()
        for d in dns:
            full = os.path.join(dp, d)
            if os.path.islink(full):
                files.append(os.path.relpath(full, tree))
            else:
                dirs.append(os.path.relpath(full, tree))
        for fn in sorted(fns):
            files.append(os.path.relpath(os.path.join(dp, fn), tree))
    files.sort(key=lambda p: (p == 'AGENTS.md', p))
    return files, dirs


IDENT = re.compile(r'[0-9]{1,25}-[0-9]{1,10}\Z')
RESERVED = (STAGING, BACKUP)


def _safe_rel(p):
    """journal 裡的路徑：相對、非空、不含 .. 與 NUL、normpath 不變、第一格不是 staging／backup。"""
    return (isinstance(p, str) and p and '\0' not in p and not p.startswith('/')
            and os.path.normpath(p) == p and '..' not in p.split('/')
            and not p.split('/')[0].startswith(RESERVED))


def _bad_journal(staging, why):
    return WfError('BadJournal', '%s/%s is not a valid wf_init journal (%s); nothing was changed. This is not '
                   'something you can fix: ask the user to inspect %s and delete it'
                   % (os.path.basename(staging), COMMIT, why, os.path.basename(staging)))


def load_journal(staging):
    """讀 commit.json 並當成不可信輸入驗一遍；不合＝BadJournal（什麼都沒寫）。"""
    try:
        with open(os.path.join(staging, COMMIT), encoding='utf-8') as f:
            plan = json.load(f)
    except (OSError, ValueError) as e:
        raise _bad_journal(staging, 'cannot read it: %s' % e)
    if not isinstance(plan, dict):
        raise _bad_journal(staging, 'not a JSON object')
    ident = plan.get('id')
    if not isinstance(ident, str) or not IDENT.match(ident) or os.path.basename(staging) != STAGING + ident:
        raise _bad_journal(staging, 'id does not match the folder name')
    if plan.get('backup') != BACKUP + ident:
        raise _bad_journal(staging, 'backup must be %s' % (BACKUP + ident))
    for key in ('files', 'dirs'):
        items = plan.get(key)
        if not isinstance(items, list):
            raise _bad_journal(staging, '%s must be a list' % key)
        for p in items:
            if not _safe_rel(p):
                raise _bad_journal(staging, 'unsafe path in %s: %r' % (key, p))
    return plan


def _inside(parent, child):
    return child == parent or child.startswith(parent.rstrip('/') + '/')


def _roll_forward(target, staging):
    """照 commit.json 把還在 staging 的檔一個個 rename 進 target；被蓋掉的舊檔挪進 .wf-backup-<id>/。
    每一步都可重做：src 不在＝已經搬過。先整份驗過（journal、目的地途中、來源在 staging/tree 裡）才動手。
    回 (搬了幾個, 備份了幾個)。"""
    plan = load_journal(staging)
    tree = os.path.join(staging, 'tree')
    if os.path.islink(tree) or not os.path.isdir(tree):
        raise _bad_journal(staging, 'tree/ is missing or a symbolic link')
    real_tree = os.path.realpath(tree)
    backup = os.path.join(target, plan['backup'])
    if os.path.islink(backup) or (os.path.lexists(backup) and not os.path.isdir(backup)):
        raise WfError('UnsafePath', '%s is not a real folder; nothing was changed. Ask the user to remove it'
                      % plan['backup'])
    _check_no_links(target, plan['files'] + plan['dirs'])
    _check_no_links(backup, plan['files'] + plan['dirs'], base=target)
    for relp in plan['files']:
        src = os.path.join(tree, relp)
        if os.path.lexists(src) and not _inside(real_tree, os.path.realpath(os.path.dirname(src))):
            raise _bad_journal(staging, '%s points outside the staging area' % relp)
    moved = backed = 0
    for d in plan['dirs']:
        dst = os.path.join(target, d)
        if os.path.isdir(dst) and not os.path.islink(dst):
            continue
        if os.path.lexists(dst):
            _backup(target, backup, d)
            backed += 1
        os.makedirs(dst, exist_ok=True)
    total = len(plan['files'])
    for i, relp in enumerate(plan['files']):
        if i == total // 2:
            _hook('commit')
        src, dst = os.path.join(tree, relp), os.path.join(target, relp)
        if not os.path.lexists(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.lexists(dst):
            _backup(target, backup, relp)
            backed += 1
        os.rename(src, dst)
        moved += 1
    shutil.rmtree(staging, ignore_errors=True)
    return moved, backed


def _backup(target, backup, relp):
    dst = os.path.join(backup, relp)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    n = 0
    while os.path.lexists(dst):
        n += 1
        dst = '%s.%d' % (os.path.join(backup, relp), n)
    os.rename(os.path.join(target, relp), dst)


def recover(target):
    """處理上次沒做完的 staging：有 commit.json＝驗過再往前做完；沒有＝丟掉。回白話清單。
    呼叫端要持專案鎖（init 會拿）。"""
    notes = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        if not name.startswith(STAGING) or os.path.islink(full) or not os.path.isdir(full):
            continue
        if os.path.lexists(os.path.join(full, COMMIT)):
            moved, backed = _roll_forward(target, full)
            notes.append('finished an interrupted import from %s (%d files moved, %d backed up)'
                         % (name, moved, backed))
        else:
            shutil.rmtree(full, ignore_errors=True)
            notes.append('discarded an unfinished staging area %s' % name)
    return notes


def _lock(target):
    """專案鎖：flock 專案資料夾本身的 fd（不建檔、不會被 rename）；拿不到＝Busy。"""
    import fcntl
    fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_CLOEXEC', 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise WfError('Busy', 'another wf_init is running on this project; wait for it to finish, then call '
                      'wf_init again')
    return fd


def init(target, flavor_list, non_invasive=None, timeout=INIT_TIMEOUT):
    """在 target 裡的 .wf-staging-<id>/ 跑快照的 wf-init.sh，成功才搬進 target。回 {'notes', 'moved', 'backed'}。
    從收拾舊 staging 到搬完、清完整段持專案鎖。"""
    known = flavors()
    bad = [f for f in flavor_list if f not in known]
    if bad:
        raise WfError('BadArguments', 'unknown flavor %s; available: %s' % (', '.join(bad), ', '.join(known)))
    os.makedirs(target, exist_ok=True)
    fd = _lock(target)
    try:
        return _init_locked(target, flavor_list, non_invasive, timeout)
    finally:
        os.close(fd)


def _init_locked(target, flavor_list, non_invasive, timeout):
    notes = recover(target)
    if os.path.lexists(os.path.join(target, 'AGENTS.md')):
        if notes:
            return {'notes': notes, 'moved': 0, 'backed': 0, 'resumed': True}
        raise WfError('AlreadyImported', 'AGENTS.md already exists in the project, so workflows is already '
                      'imported; do not run wf_init again (fix the files instead)')
    ident = '%d-%d' % (time.time_ns(), os.getpid())
    staging = os.path.join(target, STAGING + ident)
    tree = os.path.join(staging, 'tree')
    os.makedirs(tree)
    argv = ['bash', os.path.join(SNAP, 'tools', 'wf-init.sh'), '--target', tree, '--quiet']
    if flavor_list:
        argv += ['--flavor', ','.join(flavor_list)]
    if non_invasive:
        argv += ['--non-invasive', non_invasive]
    try:
        proc = subprocess.Popen(argv, cwd=target, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=_env())
        _hook('init')
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        shutil.rmtree(staging, ignore_errors=True)
        raise WfError('Timeout', 'wf-init did not finish in %d s; nothing was changed' % timeout)
    except OSError as e:
        shutil.rmtree(staging, ignore_errors=True)
        raise WfError('SpawnFailed', 'cannot run bash: %s' % (e.strerror or e))
    if proc.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        msg = (err or out).decode('utf-8', 'replace').strip().splitlines()
        raise WfError('InitFailed', 'wf-init failed (exit %d): %s; nothing was changed'
                      % (proc.returncode, msg[-1] if msg else 'no output'))
    _check_no_staging_path(tree, staging)
    files, dirs = _manifest(tree)
    try:
        _check_no_links(target, files + dirs)
    except WfError:
        shutil.rmtree(staging, ignore_errors=True)     # 這份 staging 是這次自己建的，可以刪
        raise
    _write_json(os.path.join(staging, COMMIT), {'id': ident, 'files': files, 'dirs': dirs,
                                                'backup': BACKUP + ident})
    moved, backed = _roll_forward(target, staging)
    return {'notes': notes, 'moved': moved, 'backed': backed, 'resumed': False,
            'backup': BACKUP + ident if backed else None}


def _check_no_links(top, rels, base=None):
    """要搬進去（或備份進去）的路徑，途中（不含最後一格）若有符號連結，搬的時候會寫到連結指的地方：
    先拒絕、什麼都不動（不刪任何東西，由呼叫端決定）。top 自己是連結也算。"""
    if os.path.islink(top):
        raise WfError('UnsafePath', '%s is a symbolic link; wf_init will not write through it. Nothing was '
                      'changed; ask the user to replace the link with a real folder' % os.path.relpath(top, base or top))
    for relp in rels:
        parts = relp.split(os.sep)[:-1]
        cur = top
        for part in parts:
            cur = os.path.join(cur, part)
            if os.path.islink(cur):
                raise WfError('UnsafePath', '%s in the project is a symbolic link; wf_init will not write through '
                              'it. Nothing was changed; ask the user to replace the link with a real folder'
                              % os.path.relpath(cur, base or top))
            if not os.path.exists(cur):
                break


def _check_no_staging_path(tree, staging):
    """wf-init 若把絕對路徑寫進檔，搬家後會指到已刪的 staging：寧可不搬。"""
    needle = os.path.basename(staging).encode()
    for dp, _dns, fns in os.walk(tree):
        for fn in fns:
            full = os.path.join(dp, fn)
            if os.path.islink(full):
                if needle in os.readlink(full).encode():
                    break
                continue
            with open(full, 'rb') as f:
                if needle in f.read():
                    break
        else:
            continue
        shutil.rmtree(staging, ignore_errors=True)
        raise WfError('InitFailed', 'wf-init wrote the temporary staging path into %s; nothing was changed '
                      '(this is a bug in the snapshot, tell the user)' % os.path.relpath(full, tree))


# ---------------------------------------------------------------- tabledb ----

TABLE_OPS = ('info', 'get', 'find', 'grep', 'add', 'update', 'delete', 'columns', 'slice',
             'links', 'check', 'resolve', 'fmt')


def table(root, relfile, op, index=None, fields=None, regex=None, start=None, end=None, column=None,
          timeout=60):
    """跑快照的 tabledb.py（cwd＝root）；回 (退出碼, stdout, stderr)。參數驗證由呼叫端做。"""
    tdb = os.path.join(SNAP, 'tools', 'tabledb.py')
    kv = ['%s=%s' % (k, v) for k, v in (fields or {}).items()]
    if op == 'info':
        argv = [relfile]
    elif op in ('columns',):
        argv = [relfile, op]
    elif op in ('get', 'delete'):
        argv = [relfile, op, str(index)]
    elif op in ('find', 'add'):
        argv = [relfile, op] + kv
    elif op == 'update':
        argv = [relfile, op, str(index)] + kv
    elif op == 'grep':
        argv = [relfile, op, regex]
    elif op == 'slice':
        argv = [relfile, '--slice', str(start), str(end)]
    elif op in ('links', 'check', 'fmt'):
        argv = [op, relfile]
    elif op == 'resolve':
        argv = ['resolve', relfile, str(index)] + ([column] if column else [])
    else:
        raise WfError('BadArguments', 'unknown op %s' % op)
    try:
        # -E -s：不看 PYTHON* 環境、不加使用者 site；腳本目錄（快照）在 sys.path[0]，cwd（專案）不在
        p = subprocess.run(['python3', '-E', '-s', tdb] + argv, cwd=root, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        raise WfError('Timeout', 'tabledb did not finish in %d s' % timeout)
    except OSError as e:
        raise WfError('SpawnFailed', 'cannot run python3: %s' % (e.strerror or e))
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')
