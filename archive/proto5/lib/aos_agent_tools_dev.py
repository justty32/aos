"""造工具的工具（spec/aos-agent/tools-dev.md）：aos-agent tools new／test／wrap-py。

三個都不需要 agent 家、都不叫模型：
- new：機械生一個工具包骨架（照 base 的樣子，一支範例工具＋固定案例）。
- test：在拋棄式的假 agent 家裡照 aos-agent 的方式跑工具（預設關牢），驗格式、跑自動與固定案例。
- wrap-py：用 ast 靜態讀一個 Python 檔（不 import、不執行），把有型別註解的頂層函式包成工具包。
寫檔一律先寫進同層的暫存資料夾，整包寫好才 rename 成正式名字。
這個檔是入口＋匯出層：實作分在 aos_agent_tools_dev_pack／pyread／wrappy／describe／run／test；
這裡只留 wrap_py 與 test 兩個主流程（測試換掉這裡的 jail_ready／Runner），並匯出外部用到的名字。
"""
import datetime
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from aos_agent_home import AgentError, read_tools
from aos_agent_tools import find_package

from aos_agent_tools_dev_pack import (
    _check_dest, _dump, _out_dir, _shown, BASE_COMMON, new, package_files, publish, recover
)
from aos_agent_tools_dev_pyread import analyze, tool_entry, TOOL_NAME
from aos_agent_tools_dev_wrappy import (
    _pack_name, _print_rows, _read_py, _wrap_pack, _wrap_readme, STATUS, WRAP_RUN
)
from aos_agent_tools_dev_describe import (
    apply_describe, check_describe, CONTROL, describe_with_llm, write_json_file
)
from aos_agent_tools_dev_run import jail_ready, OUTPUT_CAP, pump, Runner
from aos_agent_tools_dev_test import _single, _suite, got, load_cases, REQUIRE_JAIL_ENV


def wrap_py(file, only=None, name=None, out=None, force=False, describe=None):
    src, data, source = _read_py(file)
    pack, folder = _wrap_pack(src, name, out)
    result = analyze(source, str(src), only)
    applied = None
    if describe is not None:                      # 第三波 W3-2：照人看過的描述提案補描述（spec/aos-agent/tools-llm.md）
        applied = apply_describe(describe, result, hashlib.sha256(data).hexdigest())
    _print_rows(result)
    if not result['functions']:
        raise AgentError('NothingToWrap', '%s 沒有一支函式能包成工具（看上面的表：要頂層、非底線開頭、'
                         '每個參數都有支援的型別註解）；不寫任何檔' % src)
    _check_dest(folder, pack, force)
    tools = [tool_entry(pack, n, sig) for n, sig in result['functions'].items()]
    info = {'_type': 'aos_wrap_py', '_version': 1, 'source': str(src), 'copy': 'src/' + src.name,
            'module': re.sub(r'\W', '_', src.stem), 'sha256': hashlib.sha256(data).hexdigest(),
            'generated': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
            'functions': {n: {'line': s['line'], 'params': s['params']} for n, s in result['functions'].items()},
            'rejected': [{'name': r[0], 'line': r[3], 'reason': r[2]} for r in result['rows'] if r[1] == 'reject'],
            'skipped': [{'name': r[0], 'line': r[3], 'reason': r[2]} for r in result['rows'] if r[1] == 'skip']}
    if applied is not None:
        info['describe'] = applied
    path = _shown(folder / pack)
    files = package_files(pack, [(pack + '.json', _dump(tools), False), ('run', WRAP_RUN, True),
                                 ('src/' + src.name, data, False), ('wrap.json', _dump(info), False),
                                 ('_common.py', BASE_COMMON.read_bytes(), False),
                                 ('config.json', _dump({'root': 'workspace'}), False),
                                 ('README.md', _wrap_readme(pack, src.name, result, path), False)])
    dest = publish(folder, pack, files, force)
    print('生了 %s/：%d 支工具（%s）' % (dest, len(tools), '、'.join(result['functions'])))
    print('下一步：aos-agent tools test %s' % path)
    print('裝進家：aos-agent tools add %s --target 家' % path)
    return 0


def test(spec, args=None, case_file=None, no_jail=False, as_json=False, tool=None):
    name, folder, tools_file = find_package(spec)
    tools = read_tools([str(tools_file)])                 # 格式照 agent §3.3 驗；壞了＝ToolInvalid
    names = [t['function']['name'] for t in tools]
    if tool is not None:
        if tool not in names:
            raise AgentError('NotFound', '%s 裡沒有工具 %s（有：%s）' % (folder, tool, '、'.join(names)))
        tools = [t for t in tools if t['function']['name'] == tool]
    if args is not None and len(tools) != 1:
        raise AgentError('Usage', '--args 只跑一支：%s 有 %d 支（%s），加 --tool NAME 挑一支'
                         % (name, len(tools), '、'.join(names)))
    cases = None
    if args is None:
        path = Path(os.path.abspath(case_file)) if case_file else folder / 'cases.json'
        if case_file or path.is_file():
            cases = [c for c in load_cases(path, names) if tool is None or c['tool'] == tool]
    if no_jail:
        jail, why = False, '給了 --no-jail'
    else:
        jail, why = jail_ready()
    if not jail and os.environ.get(REQUIRE_JAIL_ENV) == '1':   # toolsmith 設的：關不了牢就一支都不跑（astra 09-25）
        raise AgentError('NoJail', '要求一定關牢（%s=1），但關不了（%s）：一支都沒跑' % (REQUIRE_JAIL_ENV, why))
    note = None if jail else '沒關牢（%s）：工具直接在這台機器上跑，碰得到你碰得到的檔' % why
    if note:                                              # 跑任何程式之前就講（卡住或崩了也看得到）
        sys.stderr.write(note + '\n')
        sys.stderr.flush()
    with tempfile.TemporaryDirectory(prefix='aos-tools-test-', ignore_cleanup_errors=True) as tmp:
        home = Path(os.path.realpath(tmp))
        shutil.copytree(folder, home / 'tools' / name, symlinks=True,
                        ignore=shutil.ignore_patterns(name + '.json', '__pycache__', '*.pyc'))
        (home / 'workspace').mkdir()
        runner = Runner(home, jail)
        if args is not None:
            return _single(runner, tools[0], args, jail, note, as_json)
        return _suite(runner, name, folder, tools, cases, jail, note, as_json)
