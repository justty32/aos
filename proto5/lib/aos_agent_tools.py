"""aos-agent tools add（aos-agent/tools.md）：裝一個工具包，或原地引用一個工具檔／資料夾。

工具包＝一個資料夾 <名>/，裡面有 <名>.json（agent.md §3.3 的工具陣列）和工具程式。
裝＝程式複製到 <家>/tools/.<名>-<版>/，符號連結 <家>/tools/<名> 原子地換過去，
工具檔最後寫到 <家>/tools/<名>.json；info.tools 沒涵蓋就補一條。原地引用＝只在 info.tools 加一條。
--as／--only 寫成 tools 元素的 $opt（agent.md §3.4）。整段持著 info.json 的 flock，寫之前整份試算。
"""
import copy
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import aos_home
from aos_agent_home import (AgentError, Context, _expand_tools, load_llm_view, read_info_doc,
                            read_tools, tool_entries)
from aos_agent_tools_edit import (DONE, commit, editable_tools, info_lock, make_entry, rel, simulate,
                                  split_entry)

PACKAGES = Path(__file__).resolve().parent.parent / 'tools'
NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]*\Z')


def find_package(spec):
    """名字（不含 /）→ proto5/tools/<名>/；含 / → 那個資料夾。回 (名, 資料夾, 工具檔)。"""
    if not spec:
        raise AgentError('Usage', 'tools add 需要工具包名字、資料夾或 .json 工具檔')
    folder = Path(os.path.abspath(os.path.expanduser(spec))) if '/' in spec else PACKAGES / spec
    name = folder.name
    if not NAME.match(name):
        hint = '；當成工具檔的話：找不到 %s' % os.path.abspath(os.path.expanduser(spec)) if spec.endswith('.json') else ''
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 開頭、不能含 .）%s' % (name, hint))
    if not folder.is_dir():
        known = sorted(p.name for p in PACKAGES.iterdir() if p.is_dir()) if PACKAGES.is_dir() else []
        hint = '；要引用目前資料夾下的資料夾請寫 ./%s' % spec if '/' not in spec and os.path.isdir(spec) else ''
        raise AgentError('NotFound', '找不到工具包 %s（%s）；內建的有：%s%s'
                         % (spec, folder, '、'.join(known) or '（無）', hint))
    tools_file = folder / (name + '.json')
    if not tools_file.is_file():
        raise AgentError('NotFound', '%s 不是工具包：裡面沒有 %s.json' % (folder, name))
    return name, folder, tools_file


def classify(spec):
    """tools add 的對象：('package', 名, 資料夾, 工具檔) 或 ('ref', 絕對路徑)。

    .json 結尾的現有檔案＝單一工具檔（原地引用；檔不在就照工具包名字驗，會是 BadName）；不含 /＝內建工具包；含 / 的資料夾有 <名>.json＝工具包，
    否則＝原地引用整個資料夾（裡面至少要有一個 *.json）。
    """
    if spec and spec.endswith('.json') and os.path.isfile(os.path.expanduser(spec)):
        return ('ref', os.path.abspath(os.path.expanduser(spec)))
    if not spec or '/' not in spec:
        return ('package',) + find_package(spec)
    folder = Path(os.path.abspath(os.path.expanduser(spec)))
    if (folder / (folder.name + '.json')).is_file() or not folder.is_dir():
        return ('package',) + find_package(spec)
    if not _expand_tools([str(folder)]):
        raise AgentError('NotFound', '%s 不是工具包（裡面沒有 %s.json），也沒有可引用的 *.json 工具檔'
                         % (folder, folder.name))
    return ('ref', str(folder))


def _options(names, where, as_arg, only):
    """--as／--only → (as, only)。as_arg：None、('one', 新名) 或 ('map', {原名: 新名})。"""
    if only is not None:
        missing = [n for n in only if n not in names]
        if missing:
            raise AgentError('ToolInvalid', '%s：--only 寫了 %s，裡面沒有這支（有：%s）'
                             % (where, '、'.join(missing), '、'.join(names) or '（無）'))
    chosen = [n for n in names if only is None or n in only]
    if as_arg is None:
        return {}, only
    if as_arg[0] == 'map':
        return dict(as_arg[1]), only
    if len(chosen) != 1:
        raise AgentError('Usage', '%s 有 %d 支工具（%s）；--as 只給新名字時結果要恰好一支，'
                         '改寫成 --as OLD=NEW[,OLD=NEW…] 或先用 --only 挑一支'
                         % (where, len(chosen), '、'.join(chosen) or '（無）'))
    return {chosen[0]: as_arg[1]}, only


def _cover(entries, target, names):
    """info.tools 哪一條已經讀到 target：同一個路徑，或它所在的資料夾（那條有 only 時要挑到其中至少一支）。"""
    for e in entries:
        if e['path'] == target:
            return e
        if e['path'] == os.path.dirname(target) and (e['only'] is None or any(n in e['only'] for n in names)):
            return e
    return None


def _entries(base):
    doc = read_info_doc(base)
    return doc, tool_entries(doc, Context(doc, base_dir=str(base)), str(base))


def add(agent_dir, spec, root=None, force=False, as_arg=None, only=None):
    base = Path(os.path.abspath(agent_dir))
    with info_lock(base):                                 # 同一個家同時只改一個（tools 與 access 共用）
        return _add(base, spec, root, force, as_arg, only)


def _add_ref(base, view, target, as_arg, only):
    """原地引用一個工具檔或資料夾：不複製，info.tools 加一條（家裡的寫相對家、家外的寫絕對）。"""
    files = _expand_tools([target])
    names = [t['function']['name'] for f in files for t in read_tools([f])]
    doc, entries = _entries(base)
    cover = _cover(entries, target, names)
    if cover is not None:
        raise AgentError('AlreadyExists', '%s 已經在 info.tools 第 %d 條（%s）；改名用 tools alias、拿掉用 tools rm'
                         % (target, cover['entry'], cover['path']))
    editable_tools(doc, '請自己把 "%s" 加進 tools' % rel(base, target))
    as_map, only = _options(names, target, as_arg, only)
    entry = make_entry(rel(base, target), as_map, only)
    root = copy.deepcopy(doc.root)
    root.setdefault('tools', []).append(entry)
    new_view = commit(base, root)
    got = [t['function']['name'] for t in new_view['tools_raw'] if t['_source']['entry'] == len(root['tools']) - 1]
    print('referenced %s（原地引用、不複製；%d 個工具：%s）' % (target, len(got), '、'.join(got)))
    print('info.json 的 tools 補了 %s' % json.dumps(entry, ensure_ascii=False))
    print(DONE)
    return 0


def _add(base, spec, root, force, as_arg, only):
    # 1. 驗（照 §1.8 的順序）：家 → 對象 → --root → 裝過沒 → 同名 → info.tools 補得補不了 → 整份試算
    view = load_llm_view(base)
    kind = classify(spec)
    if kind[0] == 'ref':
        if root is not None or force:
            raise AgentError('Usage', '--root／--force 只給裝包用；%s 是原地引用（不複製）' % kind[1])
        return _add_ref(base, view, kind[1], as_arg, only)
    name, folder, tools_file = kind[1:]
    manifest = json.loads(tools_file.read_text(encoding='utf-8'))   # 驗過的就是要寫的那份
    new_tools = read_tools([str(tools_file)])
    names = [t['function']['name'] for t in new_tools]
    if root is not None:
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            raise AgentError('NotFound', '--root %s 不是存在的資料夾' % root)
    tools_dir = base / 'tools'
    link, dest_json = tools_dir / name, tools_dir / (name + '.json')
    doc, entries = _entries(base)
    cover = _cover(entries, str(dest_json), names)
    need_entry = cover is None
    if not force and dest_json.exists() and not need_entry:
        raise AgentError('AlreadyExists', '%s 已經裝過 %s（重裝加 --force；config.json 會保留）' % (base, name))
    as_map, only = _options(names, str(tools_file), as_arg, only)
    has_opts = bool(as_map) or only is not None
    if not has_opts:
        existing = {t['function']['name']: t['_source']['file'] for t in view['tools_raw']
                    if t['_source']['file'] != str(dest_json)}
        clash = [n for n in names if n in existing]
        if clash:
            raise AgentError('ToolInvalid', '工具同名：%s（已在 %s）；先把舊的拿掉或改名'
                             % ('、'.join(clash), '、'.join(sorted({existing[n] for n in clash}))))
    info_root = None
    if need_entry or has_opts:
        editable_tools(doc, '請自己把 "tools/%s.json" 加進 tools' % name)
        info_root = copy.deepcopy(doc.root)
        entries_list = info_root.setdefault('tools', [])
        if need_entry:
            entries_list.append(make_entry('tools/%s.json' % name, as_map, only))
        elif cover['path'] == str(dest_json):             # 那條就是這個工具檔：選項整個換成這次給的
            entries_list[cover['entry']] = make_entry(split_entry(entries_list[cover['entry']])[0], as_map, only)
        else:                                             # 那條是整個資料夾：as 併進去、only 補上其他檔的
            val, old_as, old_only = split_entry(entries_list[cover['entry']])
            old_as.update(as_map)
            if only is not None:
                others = [t['_source']['name'] for t in view['tools_raw']
                          if t['_source']['entry'] == cover['entry'] and t['_source']['file'] != str(dest_json)]
                old_only = others + only
            entries_list[cover['entry']] = make_entry(val, old_as, old_only)
    simulate(base, doc.root if info_root is None else info_root, files={str(dest_json): manifest})

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
    if info_root is not None:
        commit(base, info_root, files={str(dest_json): manifest})

    # 6. 清掉舊版本與之前崩潰留下的殘渣（不是現在連結指的那個）
    ours = re.compile(r'\.%s-\d+(\.tmp|\.old|\.link-\d+)?\Z' % re.escape(name))
    for stale in tools_dir.iterdir():
        if ours.match(stale.name) and stale.name != version:
            shutil.rmtree(stale, ignore_errors=True) if stale.is_dir() and not stale.is_symlink() \
                else stale.unlink(missing_ok=True)

    names = ['%s→%s' % (n, as_map[n]) if n in as_map else n for n in names if only is None or n in only]
    print('installed %s → %s（%d 個工具：%s）' % (name, dest_json, len(names), '、'.join(names)))
    if info_root is not None:
        changed = info_root['tools'][-1] if need_entry else info_root['tools'][cover['entry']]
        print('info.json 的 tools %s %s' % ('補了' if need_entry else '第 %d 條改成' % cover['entry'],
                                           json.dumps(changed, ensure_ascii=False)))
    from aos_agent_access import access_path, ensure_default   # A2 的模組；延遲載入
    note = ensure_default(base, root if root is not None else 'workspace')
    if note:
        print(note)
    jailed = access_path(base)
    if jailed and work_root:                              # 工具包有工作根目錄才講（config.json 的 root）
        cwd, mapped = _jail_cwd(base, jailed)
        print('關牢：工具的工作根目錄＝牢裡的 /work/%s%s；看 aos-agent access ls'
              % (cwd or '', '（對到 %s）' % mapped if mapped else ''))
        print('（%s 的 root＝%s 只在不關牢時用）' % (link / 'config.json', work_root))
        if root is not None and cwd and os.path.realpath(mapped or '') != os.path.realpath(work_root):
            # access.json 早就在（例如 init 生的）：--root 不會改牢裡看到的；教一行改表
            print('要讓工具在 %s 工作：aos-agent access set %s %s --target %s'
                  % (work_root, cwd, work_root, base))
    elif work_root:
        print('工作根目錄：%s（改 %s 的 root）' % (work_root, link / 'config.json'))
    if work_root:
        real_home, real_root = os.path.realpath(base), os.path.realpath(work_root)
        if real_home == real_root or real_home.startswith(real_root.rstrip(os.sep) + os.sep):
            print('注意：工作根目錄包含 agent 家，%s' % ('access 裡把它掛成可寫會被拒（AccessUnsafe）' if jailed
                  else '模型改得到自己的 info.json、記憶與 state.json'), file=sys.stderr)
    print(DONE)
    return 0


def _jail_cwd(base, path):
    """盡量讀出 access 檔的 cwd 名字與它對到的路徑（只認字面字串）；讀不出來回 (None, None)。"""
    try:
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
        cwd = obj.get('cwd')
        value = obj.get('mounts', {}).get(cwd) if isinstance(cwd, str) else None
    except (OSError, ValueError, AttributeError):
        return None, None
    if not isinstance(value, str):
        return cwd if isinstance(cwd, str) else None, None
    return cwd, os.path.abspath(os.path.join(base, os.path.expanduser(value)))


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
