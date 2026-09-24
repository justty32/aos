"""aos-agent tools add（aos-agent.md §1.8）：把一個工具包裝進 agent 家的 tools/。

工具包＝一個資料夾 <名>/，裡面有 <名>.json（agent.md §3.3 的工具陣列）和工具程式。
裝＝程式複製到 <家>/tools/<名>/、工具檔寫到 <家>/tools/<名>.json（最後寫）；info.tools 沒涵蓋就補一條。
"""
import json
import os
import shutil
import sys
from pathlib import Path

import aos_home
from aos_agent_home import (AgentError, Context, load_llm_view, read_info_doc, read_tools,
                            resolve_field)

PACKAGES = Path(__file__).resolve().parent.parent / 'tools'


def find_package(spec):
    """名字（不含 /）→ proto5/tools/<名>/；含 / → 那個資料夾。回 (名, 資料夾, 工具檔)。"""
    if not spec:
        raise AgentError('Usage', 'tools add 需要工具包名字或資料夾')
    folder = Path(os.path.abspath(spec)) if '/' in spec else PACKAGES / spec
    name = folder.name
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
    name, folder, tools_file = find_package(spec)
    new_tools = read_tools([str(tools_file)])            # 工具包自己的檔先驗（ToolInvalid）
    dest, dest_json = base / 'tools' / name, base / 'tools' / (name + '.json')
    if root is not None:
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            raise AgentError('NotFound', '--root %s 不是存在的資料夾' % root)
    if not force and (os.path.lexists(dest) or os.path.lexists(dest_json)):
        raise AgentError('AlreadyExists', '%s 已經裝過 %s（重裝加 --force；config.json 會保留）' % (base, name))
    view = load_llm_view(base)                            # 家要讀驗得過（NotAnAgent 等）
    replaced = {os.path.abspath(dest_json)}
    existing = {t['function']['name']: p for p in view['tool_paths'] if os.path.abspath(p) not in replaced
                for t in read_tools([p])}
    clash = [t['function']['name'] for t in new_tools if t['function']['name'] in existing]
    if clash:
        raise AgentError('ToolInvalid', '工具同名：%s（已在 %s）；先把舊的拿掉或改名'
                         % ('、'.join(clash), '、'.join(sorted({existing[n] for n in clash}))))
    doc = read_info_doc(base)
    entries = resolve_field(doc, Context(doc, base_dir=str(base)), ['tools']) if 'tools' in doc.root else []
    need_entry = not _covered(base, entries, dest_json)
    if need_entry and not (isinstance(doc.root.get('tools', []), list)
                           and all(isinstance(e, str) for e in doc.root.get('tools', []))):
        raise AgentError('FieldTypeMismatch', 'info.json 的 tools 不是字面陣列，沒辦法自動補；'
                         '請自己把 "tools/%s.json" 加進 tools' % name)

    # 程式先就位（暫存資料夾→rename），工具檔最後寫：下一格看到工具檔時程式一定已經在。
    (base / 'tools').mkdir(exist_ok=True)
    tmp = base / 'tools' / ('.%s.tmp-%d' % (name, os.getpid()))
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(folder, tmp, symlinks=True,
                    ignore=shutil.ignore_patterns(name + '.json', '__pycache__', '*.pyc'))
    old_config = dest / 'config.json'
    if root is not None:
        aos_home.write_json(tmp / 'config.json', {'root': root})
    elif old_config.is_file():
        shutil.copy2(old_config, tmp / 'config.json')     # 重裝保留使用者改過的設定
    if dest.exists() or dest.is_symlink():
        trash = base / 'tools' / ('.%s.old-%d' % (name, os.getpid()))
        os.rename(dest, trash)
        os.rename(tmp, dest)
        shutil.rmtree(trash, ignore_errors=True)
    else:
        os.rename(tmp, dest)
    work_root = _work_root(base, dest)
    aos_home.write_json(dest_json, json.loads(tools_file.read_text(encoding='utf-8')))
    if need_entry:
        doc.root.setdefault('tools', []).append('tools/%s.json' % name)
        aos_home.write_json(base / 'info.json', doc.root)
    names = [t['function']['name'] for t in new_tools]
    print('installed %s → %s（%d 個工具：%s）' % (name, dest_json, len(names), '、'.join(names)))
    if need_entry:
        print('info.json 的 tools 補了 "tools/%s.json"' % name)
    if work_root:
        print('工作根目錄：%s（改 %s 的 root）' % (work_root, dest / 'config.json'))
        if str(base) == str(work_root) or str(base).startswith(str(work_root).rstrip(os.sep) + os.sep):
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
