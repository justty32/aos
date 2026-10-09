"""固定答案與隔離變體；不跑重造腳本、不匯入候選。"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

NAME = 'mailstatus'
MAIN = {'v': 1, 'statuses': {'BLOCKED': 2, 'DONE': 5, 'PROGRESS': 1, 'REQUEST': 7}}
EMPTY = {'v': 1, 'statuses': {}}
OPEN_ID = 'dave-20261009T232446-4a6808235433'


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
    issues = []
    entry = Path(top).resolve() / ('packs/' + NAME + '/bin/aos7-' + NAME)
    def run(node, expected=None, code=0, label='case'):
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
                    issues.append(label + '：答案不合：得到 ' + p.stdout.decode('utf-8', 'replace')[:300] + '；應為 ' + json.dumps(expected, ensure_ascii=False))
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
        for variant in range(3):
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
            else:
                inbox = node / 'teams/ops/inbox'
                inbox.mkdir(parents=True)
                for i, status in enumerate(('PROGRESS', 'DONE', 'FAILED')):
                    (inbox / ('broadcast' + str(i) + '.md')).write_text('---\nfrom: ops\nto: team:ops\nstatus: ' + status + '\nid: broadcast-' + str(i) + '\nre: ' + OPEN_ID + '\n---\n# 廣播\n')
                label = '團隊：再加一個 R/teams/ops/inbox/ 團隊信箱和幾封廣播（teams/ 是團隊資料夾，不是人；團隊信不算）'
            run(node, MAIN, label=label)
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
