"""aos-agent tools add（aos-agent.md §1.8）：把一個工具包裝進 agent 家的 tools/。

工具包＝一個資料夾 <名>/，裡面有 <名>.json（agent.md §3.3 的工具陣列）和工具程式。
裝＝程式複製到 <家>/tools/.<名>-<版>/，符號連結 <家>/tools/<名> 原子地換過去，
工具檔最後寫到 <家>/tools/<名>.json；info.tools 沒涵蓋就補一條。整段持著 info.json 的 flock。
"""
import fcntl
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import aos_home
from aos_agent_home import (AgentError, Context, load_llm_view, read_info_doc, read_tools,
                            resolve_field)

PACKAGES = Path(__file__).resolve().parent.parent / 'tools'
NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]*\Z')


def find_package(spec):
    """名字（不含 /）→ proto5/tools/<名>/；含 / → 那個資料夾。回 (名, 資料夾, 工具檔)。"""
    if not spec:
        raise AgentError('Usage', 'tools add 需要工具包名字或資料夾')
    folder = Path(os.path.abspath(spec)) if '/' in spec else PACKAGES / spec
    name = folder.name
    if not NAME.match(name):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 開頭、不能含 .）' % name)
    if not folder.is_dir():
        known = sorted(p.name for p in PACKAGES.iterdir() if p.is_dir()) if PACKAGES.is_dir() else []
        raise AgentError('NotFound', '找不到工具包 %s（%s）；內建的有：%s'
                         % (spec, folder, '、'.join(known) or '（無）'))
    tools_file = folder / (name + '.json')
    if not tools_file.is_file():
        raise AgentError('NotFound', '%s 不是工具包：裡面沒有 %s.json' % (folder, name))
    return name, folder, tools_file


def _covered(base, entries, tools_json):
    """info.tools 解出來的某一條是 tools/<名>.json 本身，或是它所在的資料夾。"""
    for entry in entries:
        p = os.path.abspath(os.path.join(base, entry))
        if p == str(tools_json) or p == str(tools_json.parent):
            return True
    return False


def add(agent_dir, spec, root=None, force=False):
    base = Path(os.path.abspath(agent_dir))
    with open(base / 'info.json', 'rb') as lock:           # 同一個家同時只裝一個（不寫任何檔）
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _add(base, spec, root, force)


def _add(base, spec, root, force):
    # 1. 驗（照 §1.7 的順序）：家 → 工具包 → --root → 裝過沒 → 同名 → info.tools 補得補不了
    view = load_llm_view(base)
    name, folder, tools_file = find_package(spec)
    manifest = json.loads(tools_file.read_text(encoding='utf-8'))   # 驗過的就是要寫的那份
    new_tools = read_tools([str(tools_file)])
    if root is not None:
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            raise AgentError('NotFound', '--root %s 不是存在的資料夾' % root)
    tools_dir = base / 'tools'
    link, dest_json = tools_dir / name, tools_dir / (name + '.json')
    doc = read_info_doc(base)
    entries = resolve_field(doc, Context(doc, base_dir=str(base)), ['tools']) if 'tools' in doc.root else []
    need_entry = not _covered(base, entries, dest_json)
    if not force and dest_json.exists() and not need_entry:
        raise AgentError('AlreadyExists', '%s 已經裝過 %s（重裝加 --force；config.json 會保留）' % (base, name))
    replaced = os.path.abspath(dest_json)
    existing = {t['function']['name']: p for p in view['tool_paths'] if os.path.abspath(p) != replaced
                for t in read_tools([p])}
    clash = [t['function']['name'] for t in new_tools if t['function']['name'] in existing]
    if clash:
        raise AgentError('ToolInvalid', '工具同名：%s（已在 %s）；先把舊的拿掉或改名'
                         % ('、'.join(clash), '、'.join(sorted({existing[n] for n in clash}))))
    if need_entry and not (isinstance(doc.root.get('tools', []), list)
                           and all(isinstance(e, str) for e in doc.root.get('tools', []))):
        raise AgentError('FieldTypeMismatch', 'info.json 的 tools 不是字面陣列，沒辦法自動補；'
                         '請自己把 "tools/%s.json" 加進 tools' % name)

    # 2. 新版本放進 tools/.<名>-<版>/（先 .tmp 再 rename），config.json 照 --root 或沿用舊的
    tools_dir.mkdir(exist_ok=True)
    version = '.%s-%d' % (name, time.time_ns())
    tmp = tools_dir / (version + '.tmp')
    shutil.copytree(folder, tmp, symlinks=True,
                    ignore=shutil.ignore_patterns(name + '.json', '__pycache__', '*.pyc'))
    old_config = link / 'config.json'
    if root is not None:
        aos_home.write_json(tmp / 'config.json', {'root': root})
    elif old_config.is_file():
        shutil.copy2(old_config, tmp / 'config.json')     # 重裝保留使用者改過的設定
    os.rename(tmp, tools_dir / version)
    work_root = _work_root(base, tools_dir / version)

    # 3. tools/<名> 換成指向新版本的符號連結：rename 蓋過舊連結是原子的，tick 看不到「程式不在」的空窗。
    new_link = tools_dir / ('%s.link-%d' % (version, os.getpid()))
    os.symlink(version, new_link)
    if os.path.lexists(link) and not link.is_symlink():   # 舊式（真資料夾）或別的東西：只有這次有空窗
        os.rename(link, tools_dir / (version + '.old'))
    os.replace(new_link, link)

    # 4. 工具檔最後寫；5. info.tools 補一條
    aos_home.write_json(dest_json, manifest)
    if need_entry:
        doc.root.setdefault('tools', []).append('tools/%s.json' % name)
        aos_home.write_json(base / 'info.json', doc.root)

    # 6. 清掉舊版本與之前崩潰留下的殘渣（不是現在連結指的那個）
    ours = re.compile(r'\.%s-\d+(\.tmp|\.old|\.link-\d+)?\Z' % re.escape(name))
    for stale in tools_dir.iterdir():
        if ours.match(stale.name) and stale.name != version:
            shutil.rmtree(stale, ignore_errors=True) if stale.is_dir() and not stale.is_symlink() \
                else stale.unlink(missing_ok=True)

    names = [t['function']['name'] for t in new_tools]
    print('installed %s → %s（%d 個工具：%s）' % (name, dest_json, len(names), '、'.join(names)))
    if need_entry:
        print('info.json 的 tools 補了 "tools/%s.json"' % name)
    if work_root:
        print('工作根目錄：%s（改 %s 的 root）' % (work_root, link / 'config.json'))
        real_home, real_root = os.path.realpath(base), os.path.realpath(work_root)
        if real_home == real_root or real_home.startswith(real_root.rstrip(os.sep) + os.sep):
            print('注意：工作根目錄包含 agent 家，模型改得到自己的 info.json、記憶與 state.json', file=sys.stderr)
    print('下一格就生效，不用重 start')
    return 0


def _work_root(base, dest):
    """工具包有 config.json 的 root：相對的算在 agent 家底下、不在就建；回絕對路徑。"""
    cfg = dest / 'config.json'
    if not cfg.is_file():
        return None
    try:
        root = json.loads(cfg.read_text(encoding='utf-8')).get('root')
    except (ValueError, AttributeError):
        return None
    if not isinstance(root, str) or not root:
        return None
    full = Path(os.path.abspath(os.path.join(base, os.path.expanduser(root))))
    if not os.path.isabs(os.path.expanduser(root)):
        full.mkdir(parents=True, exist_ok=True)
    return full
