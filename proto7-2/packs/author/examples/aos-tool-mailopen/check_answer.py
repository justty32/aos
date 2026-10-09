"""主樣本自檢與隔離變體；不跑重造腳本、不匯入候選。"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

NAME = 'mailopen'
MAIN = {'v': 1, 'open': ['bob-20261009T232446-de2a6e248217', 'bob-20261009T232446-f716842f110d', 'dave-20261009T232446-4a6808235433']}
EMPTY = {'v': 1, 'open': []}
OPEN_ID = 'dave-20261009T232446-4a6808235433'


def reference(root):
    """按個人信箱慣例讀信，供自檢與答案會變的測資使用。"""
    people, records = {}, []
    for box in sorted(Path(root).iterdir()):
        inbox = box / 'inbox'
        if (box.name.startswith('.') or box.name == 'teams' or
                not box.is_dir() or box.is_symlink() or
                not inbox.is_dir() or inbox.is_symlink()):
            continue
        letters = []
        for folder in (inbox, inbox / 'done'):
            if not folder.is_dir() or folder.is_symlink():
                continue
            for path in sorted(folder.glob('*.md')):
                if path.name.startswith('.') or not path.is_file() or path.is_symlink():
                    continue
                lines = path.read_text(encoding='utf-8').splitlines()
                if not lines or lines[0] != '---' or '---' not in lines[1:]:
                    continue
                end = lines.index('---', 1)
                letters.append(dict(line.split(': ', 1) for line in lines[1:end] if ': ' in line))
        people[box.name] = {'letters': len(letters),
                            'requests': sum(r.get('status') == 'REQUEST' for r in letters)}
        records.extend(letters)
    closed = {r.get('re') for r in records if r.get('status') in ('DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED')}
    return {'v': 1, 'open': sorted(r['id'] for r in records if r.get('status') == 'REQUEST' and r['id'] not in closed)}


def change_letters(root):
    """只改隔離複本：兩封終局回信、一封新請求、減一封進度信。"""
    additions = (
        ('alice/inbox/variant-needs-user.md', 'bob', 'alice', 'NEEDS-USER', 'variant-needs-user', OPEN_ID),
        ('bob/inbox/variant-request.md', 'erin', 'bob', 'REQUEST', 'variant-erin-request', ''),
        ('carol/inbox/done/variant-failed.md', 'alice', 'carol', 'FAILED', 'variant-failed', 'bob-20261009T232446-f716842f110d'),
    )
    for relative, sender, recipient, status, ident, reply in additions:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\nfrom: ' + sender + '\nto: ' + recipient +
                        '\nstatus: ' + status + '\nat: 2026-10-09T00:00:00+08:00' +
                        '\nreply-to: ' + sender + '/inbox\nid: ' + ident +
                        '\nre: ' + reply + '\n---\n# 增減測資\n', encoding='utf-8')
    (root / 'dave/inbox/20261009T2324-carol-PROGRESS.md').unlink()
    (root / 'frank/inbox').mkdir(parents=True)


def partial_reply():
    # 信頭完整，正文仍未寫完；錯誤掃描會誤以為此請求已結案。
    return '---\nfrom: carol\nto: dave\nstatus: DONE\nat: 2026-10-09T00:00:00+08:00\nreply-to: carol/inbox\nid: variant-partial\nre: ' + OPEN_ID + '\n---\n# 已檢'


def sorted_keys(actual):
    if not isinstance(actual, dict):
        return False
    key = next(k for k in EMPTY if k != 'v')
    value = actual.get(key)
    return not isinstance(value, dict) or list(value) == sorted(value)


def snapshot(root):
    """只用 lstat，不跟隨連結；允許快取目錄。"""
    result = {}
    def visit(path):
        st = os.lstat(path)
        kind = stat.S_IFMT(st.st_mode)
        content = path.read_bytes() if stat.S_ISREG(st.st_mode) else os.readlink(path) if stat.S_ISLNK(st.st_mode) else None
        result[path.relative_to(root).as_posix()] = (kind, st.st_size, stat.S_IMODE(st.st_mode), st.st_mtime_ns, content, stat.S_ISDIR(st.st_mode) and os.path.lexists(path / '__pycache__'))
        if stat.S_ISDIR(st.st_mode):
            for name in sorted(os.listdir(path)):
                if name != '__pycache__':
                    visit(path / name)
    visit(root)
    return result


def same_snapshot(before, after):
    if before.keys() != after.keys():
        return False
    for key, old in before.items():
        new = after[key]
        if old == new:
            continue
        # 快取出現或消失會改父目錄大小與時間；仍核對型別、權限和可見子項。
        if old[0] == new[0] == stat.S_IFDIR and old[5] != new[5] and old[2] == new[2]:
            continue
        return False
    return True


def exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def readonly(node):
    modes = []
    for path in [node, *node.rglob('*')]:
        st = os.lstat(path)
        if not stat.S_ISLNK(st.st_mode):
            modes.append((path, stat.S_IMODE(st.st_mode)))
            path.chmod(stat.S_IMODE(st.st_mode) & ~0o222)
    return modes


def check_answer(top, fixture):
    try:
        if reference(fixture) != MAIN:
            return dict(ok=False, issues=['檢查器自檢失敗'])
    except (OSError, ValueError, KeyError):
        return dict(ok=False, issues=['檢查器自檢失敗'])
    issues = []
    entry = Path(top).resolve() / ('packs/' + NAME + '/bin/aos7-' + NAME)
    def run(node, expected=None, code=0, label='case', reveal_expected=True):
        # 父目錄快照也涵蓋不存在／檔案輸入與旁邊的副作用。
        before = snapshot(node.parent)
        try:
            p = subprocess.run([sys.executable, '-B', str(entry), str(node)], capture_output=True, timeout=15)
            if p.returncode != code:
                issues.append(label + ': 退出碼不合：' + str(p.returncode))
            if code == 2:
                if p.stdout:
                    issues.append(label + ': 錯誤路徑 stdout 應空')
            elif len(p.stdout.splitlines()) != 1:
                issues.append(label + ': 答案、型別或一行 stdout 不合：' + p.stdout.decode('utf-8', 'replace')[:300])
            else:
                try:
                    actual = json.loads(p.stdout)
                except ValueError:
                    actual = None
                if not exact(actual, expected) or not sorted_keys(actual):
                    issue = label + '：答案不合：得到 ' + p.stdout.decode('utf-8', 'replace')[:300]
                    if reveal_expected:
                        issue += '；應為 ' + json.dumps(expected, ensure_ascii=False)
                    issues.append(issue)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            issues.append(label + ': ' + str(exc))
        finally:
            try:
                unchanged = same_snapshot(before, snapshot(node.parent))
            except OSError:
                unchanged = False
            if not unchanged:
                issues.append(label + ': 輸入／父目錄的型別、大小、權限、mtime_ns 或內容被修改')
    original = Path(fixture).resolve()
    run(original, MAIN, label='主樣本（真郵局）')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for variant in range(4):
            node = root / str(variant)
            shutil.copytree(original, node, symlinks=True)
            if variant == 0:
                for box in node.iterdir():
                    inbox = box / 'inbox'
                    if box.name.startswith('.') or box.name == 'teams' or not inbox.is_dir():
                        continue
                    for path in inbox.glob('*.md'):
                        if path.name.startswith('.'):
                            continue
                        done = inbox / 'done'
                        done.mkdir(exist_ok=True)
                        path.rename(done / path.name)
                label = '已辦結：把每個人 inbox/ 頂層的信全搬進同一人的 inbox/done/（辦結的信歸檔在 <人>/inbox/done/，仍是那個人的信）'
            elif variant == 1:
                inbox = node / 'dave/inbox'
                partial = partial_reply()
                staging = inbox / '.tmp'
                staging.mkdir(exist_ok=True)
                (staging / 'tmpvariant').write_text(partial)
                (inbox / '.draft.md').write_text(partial)
                label = '暫存：再放一份 <人>/inbox/.tmp/ 寫到一半的信和一個 .draft.md（. 開頭的檔與資料夾都不是信）'
            elif variant == 2:
                inbox = node / 'teams/ops/inbox'
                inbox.mkdir(parents=True)
                for i, status in enumerate(('PROGRESS', 'DONE', 'FAILED')):
                    (inbox / ('broadcast' + str(i) + '.md')).write_text('---\nfrom: ops\nto: team:ops\nstatus: ' + status + '\nid: broadcast-' + str(i) + '\nre: ' + OPEN_ID + '\n---\n# 廣播\n')
                label = '團隊：再加一個 R/teams/ops/inbox/ 團隊信箱和幾封廣播（teams/ 是團隊資料夾，不是人；團隊信不算）'
            else:
                change_letters(node)
                label = '增減：加減幾封信、加一個空信箱（答案會變，不能背主樣本）'
            run(node, reference(node) if variant == 3 else MAIN, label=label,
                reveal_expected=variant != 3)
        ro = root / 'readonly'
        shutil.copytree(original, ro, symlinks=True)
        modes = readonly(ro)
        try:
            run(ro, MAIN, label='readonly')
        finally:
            for path, mode in modes:
                path.chmod(mode)
        file = root / 'file'
        file.write_text('not a directory')
        for node in (root / 'absent', file):
            run(node, code=2)
        empty = root / 'empty'
        empty.mkdir()
        (empty / 'ignored-link').symlink_to(root / 'absent-target')
        run(empty, EMPTY, label='空郵局')
    return dict(ok=not issues, issues=issues)


if __name__ == '__main__':
    answer = check_answer(*sys.argv[1:]) if len(sys.argv) == 3 else dict(ok=False, issues=['用法：check_answer.py <proto根> <fixture>'])
    print(json.dumps(answer, ensure_ascii=False))
    raise SystemExit(0 if answer['ok'] else 1)
