"""造工具共用：整包先寫暫存資料夾再 rename 就位（含 --force 備份與殘渣回收），以及 `tools new` 生骨架。"""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

from aos_agent_home import AgentError
from aos_agent_tools import NAME, PACKAGES


BASE_COMMON = PACKAGES / 'base' / '_common.py'


# ------------------------------------------------------------------ 共用：寫一整包 ----

def _mode(executable):
    umask = os.umask(0)
    os.umask(umask)
    return (0o777 if executable else 0o666) & ~umask


def _out_dir(out):
    folder = Path(os.path.abspath(os.path.expanduser(out or '.')))
    if not folder.is_dir():
        raise AgentError('NotFound', '--out %s 不是存在的資料夾' % folder)
    return folder


def _check_dest(folder, name, force):
    dest = folder / name
    if os.path.lexists(dest):
        if not force:
            raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % dest)
        if dest.is_symlink() or not dest.is_dir():
            raise AgentError('AlreadyExists', '%s 不是資料夾（或是符號連結），--force 也不蓋' % dest)
    return dest


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def recover(folder, name):
    """清前一次被硬中止留下的殘渣（名字帶 pid，那個行程還活著的不碰）：
    .NAME.new-<pid>-* 直接刪；.NAME.old-<pid>-* 是 --force 的備份——正式包在就刪，
    正式包不在（崩在「舊的改名」與「新的就位」之間）就改回正式名。回印給人看的話（清單）。"""
    notes = []
    pattern = re.compile(r'\.%s\.(new|old)-(\d+)-' % re.escape(name))
    for entry in sorted(folder.iterdir()):
        m = pattern.match(entry.name)
        if not m or _alive(int(m.group(2))) or entry.is_symlink() or not entry.is_dir():
            continue
        dest = folder / name
        if m.group(1) == 'old' and not os.path.lexists(dest):
            os.rename(entry, dest)
            notes.append('上次 --force 中斷：把舊包 %s 改回 %s' % (entry.name, dest))
        else:
            shutil.rmtree(entry, ignore_errors=True)
            notes.append('清掉上次中斷留下的 %s' % entry)
    return notes


def publish(folder, name, files, force=False):
    """files＝{相對路徑: (內容 str 或 bytes, 可執行?)}；寫進 folder/.name.new-<pid>-XXXX/ 再 rename 成 folder/name。
    --force：舊包先改名成 .name.old-<pid>-…，新包就位才刪它；新包 rename 失敗就把舊包改回來。"""
    for note in recover(folder, name):
        print(note, file=sys.stderr)
    dest = _check_dest(folder, name, force)
    tmp = Path(tempfile.mkdtemp(dir=folder, prefix='.%s.new-%d-' % (name, os.getpid())))
    old = None
    try:
        for rel, (content, executable) in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            data = content.encode('utf-8') if isinstance(content, str) else content
            path.write_bytes(data)
            os.chmod(path, _mode(executable))
        for sub in [tmp] + [p for p in tmp.rglob('*') if p.is_dir()]:
            os.chmod(sub, _mode(True))
        if os.path.lexists(dest):
            _check_dest(folder, name, force)                  # 寫檔這段時間裡被換成別的東西就不蓋
            old = folder / ('.%s.old-%d-%d' % (name, os.getpid(), time.time_ns()))
            os.rename(dest, old)
        try:
            os.rename(tmp, dest)
        except BaseException:
            if old is not None and not os.path.lexists(dest):
                os.rename(old, dest)                          # 新的沒就位：舊的放回去
                old = None
            raise
        tmp = None
        if old is not None:
            shutil.rmtree(old, ignore_errors=True)            # 新的就位了才刪備份
            old = None
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    return dest


def package_files(name, entries):
    """[(相對路徑, 內容, 可執行?)] → dict；同一個路徑出現兩次＝包名撞到必要檔（BadName），不靜默蓋掉。"""
    files = {}
    for rel, content, executable in entries:
        if rel in files:
            raise AgentError('BadName', '包名 %r 會讓 %s 跟包裡另一個必要檔撞名（例如工具描述被設定檔蓋掉）；換個名字'
                             % (name, rel))
        files[rel] = (content, executable)
    return files


def _shown(dest):
    """印給人看、也能直接貼給 tools test／tools add 的路徑：目前資料夾底下的寫 ./相對，其他寫絕對。"""
    rel = os.path.relpath(dest)
    return './' + rel if not rel.startswith('..') and not os.path.isabs(rel) else str(dest)


# ------------------------------------------------------------------ tools new ----

NEW_PROGRAM = '''#!/usr/bin/env python3
"""{name}：範例工具（aos-agent tools new 生的骨架）。改 main() 的本體；參數寫在 {name}.json。

約定（proto5/tools/README.md）：stdin 收 arguments JSON；成功回純文字、退 0；
失敗用 fail(代號, 白話) —— 最後一行印 {{"ok": false, "error", "message"}}、退 1。
"""
import sys
sys.dont_write_bytecode = True
from _common import run, arg, fail  # noqa: E402


def main(args, root):
    """args＝模型給的參數（已確定是 JSON 物件）；root＝工作根目錄（關牢時是牢裡的 /work/ws）。"""
    text = arg(args, 'text', str, required=True)      # 缺了或型別錯 → BadArguments
    count = arg(args, 'count', int, 1)
    if count < 1:
        fail('BadArguments', 'count must be >= 1')
    # TODO: 在這裡寫你的程式（碰檔案用 _common.resolve(root, path) 把路徑關在工作根目錄裡）
    return ' '.join([text] * count)


if __name__ == '__main__':
    sys.exit(run(main))
'''

NEW_README = '''# {name} — 工具包（aos-agent tools new 生的骨架）

一支範例工具 `{name}`：把 `text` 重複 `count` 次。照下面改成你要的。

| 檔 | 做什麼 |
|---|---|
| `{name}.json` | 給模型看的工具描述（英文、越短越好）＋`_meta.argv`（`tools/{name}/{name}`，相對 agent 家） |
| `{name}` | 工具程式（要有執行位）：stdin 收 arguments JSON，成功印純文字退 0，失敗 `fail(代號, 訊息)` |
| `_common.py` | base 包那份的副本（讀參數、工作根目錄、錯誤格式）；**不要改**，要更新就從 `proto5/tools/base/` 再複製一次 |
| `config.json` | `root`＝不關牢時的工作根目錄（相對 agent 家） |
| `cases.json` | 固定案例，`tools test` 會跑 |

## 改

1. 改 `{name}` 的 `main()`：用 `arg(args, 名, 型別, 預設, required=)` 取參數，`# TODO` 那裡寫本體。
2. 改 `{name}.json`：`description` 一句話、`parameters` 照 JSON Schema 寫，跟程式取的參數對上。
3. 改 `cases.json`：每條 `{{"tool", "args", "expect": "ok" 或錯誤代號, "contains": 輸出要含的字}}`。

## 試

```sh
aos-agent tools test {path}             # 預設關在牢裡跑（有 bwrap 時）；--no-jail 直接跑
aos-agent tools test {path} --args '{{"text": "hi", "count": 2}}'   # 只跑一次，看原樣輸出
```

會驗工具檔格式、描述多長（token 粗估）、從 `parameters` 自動生的案例（正例、型別錯、缺必填、參數不是物件），再跑 `cases.json`。

## 裝

```sh
aos-agent tools add {path} --target 家
```

沒寫 `_jail`＝預設關牢：家裡有 `access.json` 時，工具被關進 bwrap 跑，只看得到 access.json 掛進去的資料夾。
'''


def new_files(name, path):
    """tools new 生的整包：{相對路徑: (內容, 可執行?)}。"""
    tool = [{'type': 'function',
             'function': {'name': name,
                          'description': 'Example tool: repeat text. Replace with what your tool does.',
                          'parameters': {'type': 'object',
                                         'properties': {'text': {'type': 'string', 'description': 'Text to repeat.'},
                                                        'count': {'type': 'integer', 'minimum': 1,
                                                                  'description': 'How many times (default 1).'}},
                                         'required': ['text']}},
             '_meta': {'argv': ['tools/%s/%s' % (name, name)]}}]
    cases = [{'name': 'repeat', 'tool': name, 'args': {'text': 'hi', 'count': 2}, 'expect': 'ok', 'contains': 'hi hi'},
             {'name': 'missing-text', 'tool': name, 'args': {'count': 2}, 'expect': 'BadArguments'},
             {'name': 'count-not-int', 'tool': name, 'args': {'text': 'hi', 'count': 'x'}, 'expect': 'BadArguments'},
             {'name': 'count-zero', 'tool': name, 'args': {'text': 'hi', 'count': 0}, 'expect': 'BadArguments'}]
    return [(name + '.json', _dump(tool), False),
            (name, NEW_PROGRAM.format(name=name), True),
            ('_common.py', BASE_COMMON.read_bytes(), False),
            ('config.json', _dump({'root': 'workspace'}), False),
            ('cases.json', _dump(cases), False),
            ('README.md', NEW_README.format(name=name, path=path), False)]


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def new(name, out=None, force=False):
    if not NAME.match(name):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 或 - 開頭）' % name)
    folder = _out_dir(out)
    path = _shown(folder / name)
    files = package_files(name, new_files(name, path))   # new config／new cases 在這裡擋
    _check_dest(folder, name, force)
    dest = publish(folder, name, files, force)
    print('生了 %s/：%s' % (dest, '、'.join(files)))
    print('下一步：改 %s/%s 與 %s.json，然後 aos-agent tools test %s' % (path, name, name, path))
    print('裝進家：aos-agent tools add %s --target 家' % path)
    return 0
