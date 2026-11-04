"""aos-agent tools wrap-cli（spec/aos-agent/tools-llm.md，第三波 W3-2）：把一支命令列指令包成一支工具。

參數表（spec）怎麼來，三選一：
- 機械版（預設）：CMD 是有 argparse 的 .py → 用 ast 靜態讀 add_argument（不 import、不執行）；
  其他 → 拿 help 文字（--help-file，或跑 `CMD --help`），用規則解 usage 行與選項行。解不出來的列出來，不猜。
- --describe-with-llm：help 文字（或 argparse 那段原始碼）送模型一次，回固定格式的參數表；機械檢查兜底
  （旗標要在原文逐字出現、型別只准那幾種、名字合法），不過的那格丟掉。**不產包**，只寫提案檔等人看。
- --spec FILE：照人看過（可能改過）的參數表產包，不叫模型；help 文字的 sha256 對不上＝拒（help 變了）。
產包重用 tools_dev 的 publish／package_files（暫存資料夾＋rename、--force、BadName）。
產的 run：stdin 的 arguments → argv（不經 shell）→ 跑指令、回 stdout；退出碼非 0＝CommandFailed。
這個檔是入口：拿 help 文字（測試會改這裡的 HELP_TIMEOUT）、主流程（load_spec／wrap_cli）與對照用 score；
實作分在 aos_agent_tools_wrapcli_const／argparse／helptext／check／pack，這裡匯出外部用到的名字。
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from aos_agent_home import AgentError
from aos_agent_tools import NAME
import aos_agent_tools_dev as dev

from aos_agent_tools_wrapcli_const import CONTROL, FIXED, MAX_TIMEOUT, RUN_TIMEOUT, SPEC_TYPE
from aos_agent_tools_wrapcli_argparse import argparse_segment, read_argparse, uses_argparse
from aos_agent_tools_wrapcli_helptext import parse_help
from aos_agent_tools_wrapcli_check import check_params, llm_table
from aos_agent_tools_wrapcli_pack import _exec, _pack_files, print_table

HELP_TIMEOUT = 10               # 跑 CMD --help 最多等幾秒
HELP_CAP = 256 * 1024           # help 文字最多收多少位元組


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


# ------------------------------------------------------------------ 指令與 help 文字 ----

ESC = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|.\x08')


def clean_help(text):
    """去掉終端機控制碼（GNU coreutils 會印超連結與粗體）、backspace 疊字、tab 換空白、行尾空白。"""
    text = ESC.sub('', text.replace('\r\n', '\n'))
    return '\n'.join(line.expandtabs(8).rstrip() for line in text.split('\n')).strip('\n') + '\n'


def resolve_cmd(cmd):
    """CMD → {'kind': 'file', 'path', 'py', 'data'}（檔，產包時存副本）或 {'kind': 'path', 'name'}（PATH 上的指令）。"""
    if '/' in cmd or (cmd.endswith('.py') and os.path.exists(cmd)):
        path = Path(os.path.abspath(os.path.expanduser(cmd)))
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise AgentError('NotFound', '找不到 %s' % path)
        except IsADirectoryError:
            raise AgentError('NotFound', '%s 是資料夾，不是指令' % path)
        except OSError as e:
            raise AgentError('ReadFailed', '讀不到 %s：%s' % (path, e.strerror or e))
        return {'kind': 'file', 'path': path, 'py': path.suffix == '.py', 'data': data}
    if shutil.which(cmd) is None:
        raise AgentError('NotFound', '找不到指令 %s（PATH 上沒有；檔案請寫路徑，例如 ./%s）' % (cmd, cmd))
    return {'kind': 'path', 'name': cmd}


def read_help_file(path):
    p = Path(os.path.abspath(os.path.expanduser(path)))
    try:
        data = p.read_bytes()[:HELP_CAP]
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 --help-file %s' % p)
    except OSError as e:
        raise AgentError('ReadFailed', '讀不到 --help-file %s：%s' % (p, e.strerror or e))
    return clean_help(data.decode('utf-8', 'replace')), str(p)


def run_help(info):
    """跑 `CMD --help`（這一步真的會執行 CMD）：不經 shell、stdin 關、最小環境（PATH、LANG／LC_ALL=C、HOME＝拋棄式資料夾，
    不繼承金鑰）、cwd＝那個拋棄式資料夾。輸出邊讀邊丟（各只留 HELP_CAP），10 秒到了砍整個群組；主行程結束後
    管子被另開 session 的子孫握著也最多再收 2 秒（tools_dev.pump）。stdout 空就拿 stderr。"""
    if info['kind'] == 'file':
        argv = ['python3', str(info['path'])] if info['py'] else [str(info['path'])]
    else:
        argv = [info['name']]
    argv.append('--help')
    home = tempfile.mkdtemp(prefix='aos-wrapcli-help-')
    env = {'PATH': os.environ.get('PATH') or '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': home}
    try:
        try:
            p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env, cwd=home, start_new_session=True)
        except OSError as e:
            raise AgentError('HelpFailed', '跑不起來 %s：%s' % (' '.join(argv), e.strerror or e))
        code, out, err, timed_out, _, _ = dev.pump(p, b'', HELP_TIMEOUT, HELP_CAP)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    if timed_out:
        raise AgentError('HelpFailed', '%s 跑了 %d 秒還沒結束，砍掉了；改用 --help-file' % (' '.join(argv), HELP_TIMEOUT))
    text = out if out.strip() else err
    if not text.strip():
        raise AgentError('HelpFailed', '%s 什麼都沒印（退出碼 %s）；改用 --help-file' % (' '.join(argv), code))
    return clean_help(text.decode('utf-8', 'replace'))


# ------------------------------------------------------------------ 主流程 ----

def _evidence(info, help_file, spec_data=None):
    """回 (mode, 原文, help_file 絕對路徑或 None)。--help-file 優先；--spec 記了 help_file 就用它；
    .py 有 argparse＝argparse；其他跑 CMD --help。"""
    if help_file is None and spec_data and spec_data.get('mode') == 'help' and spec_data.get('help_file'):
        help_file = spec_data['help_file']
    if help_file is not None:
        text, path = read_help_file(help_file)
        return 'help', text, path
    if info['kind'] == 'file' and info['py']:
        try:
            source = info['data'].decode('utf-8')
        except UnicodeDecodeError:
            raise AgentError('ReadFailed', '%s 不是 UTF-8 文字檔' % info['path'])
        if uses_argparse(source):
            return 'argparse', source, None
    return 'help', run_help(info), None


def load_spec(path):
    p = Path(os.path.abspath(os.path.expanduser(path)))
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 --spec %s' % p)
    except (OSError, ValueError, UnicodeError) as e:
        raise AgentError('SpecInvalid', '讀不了 --spec %s：%s' % (p, e))
    if not isinstance(data, dict) or data.get('_type') != SPEC_TYPE or data.get('_version') != 1:
        raise AgentError('SpecInvalid', '%s 不是 wrap-cli 參數表（要 _type %s、_version 1）' % (p, SPEC_TYPE))
    bad = spec_problems(data)
    if bad:
        raise AgentError('SpecInvalid', '%s 的頂層欄位不對：%s' % (p, '；'.join(bad)))
    return data, p


def spec_problems(data):
    """參數表頂層欄位一次驗完（審查 M9）：回問題清單，空＝沒問題。"""
    bad = []
    if not isinstance(data.get('command'), str) or not data['command']:
        bad.append('command 要是非空字串')
    if data.get('mode') not in ('help', 'argparse'):
        bad.append('mode 要是 help 或 argparse')
    if not isinstance(data.get('help_sha256'), str):
        bad.append('help_sha256 要是字串')
    if data.get('help_file') is not None and (not isinstance(data['help_file'], str) or not data['help_file']):
        bad.append('help_file 要是非空字串或 null')
    desc = data.get('description')
    if desc is not None and (not isinstance(desc, str) or len(desc) > 1000 or CONTROL.search(desc)):
        bad.append('description 要是字串或 null（≤ 1000 字、不含控制字元）')
    if not isinstance(data.get('params'), list):
        bad.append('params 要是陣列')
    t = data.get('timeout', RUN_TIMEOUT)
    if not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= MAX_TIMEOUT:
        bad.append('timeout 要是 1～%d 的整數（秒）' % MAX_TIMEOUT)
    return bad


def _same_cmd(a, b):
    norm = (lambda c: os.path.abspath(os.path.expanduser(c)) if '/' in c or c.endswith('.py') else c)
    return norm(a) == norm(b)


def wrap_cli(cmd, name=None, out=None, force=False, help_file=None, describe_with_llm=False, model=None,
             spec=None, ask=None):
    info = resolve_cmd(cmd)
    stem = info['path'].stem if info['kind'] == 'file' else info['name']
    pack = name if name is not None else dev._pack_name(stem)
    if not NAME.match(pack) or not dev.TOOL_NAME.match(pack.replace('-', '_')):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 或 - 開頭，≤ 64 字）' % pack)
    folder = dev._out_dir(out)
    dev.package_files(pack, [(pack + '.json', '', False)] + [(f, '', False) for f in FIXED])   # 先擋撞名
    command = str(info['path']) if info['kind'] == 'file' else info['name']
    spec_data = spec_path = None
    if spec is not None:
        spec_data, spec_path = load_spec(spec)
    mode, evidence, hf = _evidence(info, help_file, spec_data)
    sha = _sha(evidence)
    base = {'_type': SPEC_TYPE, '_version': 1, 'command': command, 'mode': mode, 'help_sha256': sha,
            'help_file': hf, 'generated': _now()}
    if spec_data is not None:
        if not _same_cmd(spec_data.get('command', ''), command):
            raise AgentError('SpecMismatch', '參數表是給 %s 的，不是 %s' % (spec_data.get('command'), command))
        if spec_data['mode'] != mode:
            raise AgentError('SpecMismatch', '參數表的來源是 %s，這次讀到的是 %s' % (spec_data['mode'], mode))
        if spec_data.get('help_sha256') != sha:
            raise AgentError('HelpChanged', '%s 跟參數表記的不一樣了（sha256 %s… ≠ %s…）；重新提案或重新機械解析'
                             % ('help 文字' if mode == 'help' else '原始碼', sha[:12], str(spec_data.get('help_sha256'))[:12]))
        params, dropped = check_params(spec_data['params'], evidence)
        if dropped:
            raise AgentError('SpecInvalid', '參數表有 %d 格沒過機械檢查：%s' % (
                len(dropped), '；'.join('%s：%s' % d for d in dropped)))
        if not params:
            raise AgentError('NothingToWrap', '參數表是空的')
        spec_out = dict(base, made_by='spec', from_spec=str(spec_path), description=spec_data.get('description'),
                        params=params, timeout=spec_data.get('timeout', RUN_TIMEOUT))
        print_table(params)
        return _publish(pack, folder, spec_out, info, force)
    if describe_with_llm:
        import aos_llm_ask
        target = folder / (pack + '.wrapcli.json')
        if os.path.lexists(target) and not force:          # 問模型之前先擋，免得白花一次
            raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % target)
        desc, params, dropped, got = llm_table(os.path.basename(command), mode,
                                               argparse_segment(evidence) if mode == 'argparse' else evidence,
                                               alias=model, ask=ask)
        # argparse 模式：旗標逐字檢查拿整份原始碼（段落是它的子集，結果一樣）
        proposal = dict(base, made_by='llm', model=got.get('model'), alias=got.get('alias'), usage=got.get('usage'),
                        ms=got.get('ms'),
                        description=desc, params=params, dropped=[{'item': a, 'reason': b} for a, b in dropped],
                        timeout=RUN_TIMEOUT)
        print_table(params, dropped=dropped)
        print(aos_llm_ask.usage_line(got), file=sys.stderr)
        dev.write_json_file(target, proposal, force)
        print('提案寫在 %s（%d 格收、%d 格丟掉；還沒產包）' % (target, len(params), len(dropped)))
        print('看過沒問題（可以先改提案檔；這一步不叫模型）：aos-agent tools wrap-cli %s --spec %s --name %s%s' % (
            shlex.quote(cmd), shlex.quote(dev._shown(target)), shlex.quote(pack),
            ' --out %s' % shlex.quote(out) if out else ''))
        return 0
    parsed = read_argparse(evidence, command) if mode == 'argparse' else parse_help(evidence)
    params, dropped = check_params(parsed['params'], evidence)   # 機械版照理全過；沒過的也列出來
    desc = parsed['description']
    print_table(params, parsed['rows'], parsed['unparsed'], dropped, parsed['notes'])
    if not params:
        raise AgentError('NothingToWrap', '%s 沒解出任何參數（看上面的表）；要包就自己寫一份參數表給 --spec' % command)
    spec_out = dict(base, made_by='mechanical', description=desc, params=params, timeout=RUN_TIMEOUT,
                    rejected=[{'item': r[1], 'line': r[3], 'reason': r[2]} for r in parsed['rows'] if r[0] != 'ok'],
                    unparsed=[{'line': u[0], 'text': u[1], 'reason': u[2]} for u in parsed['unparsed']])
    return _publish(pack, folder, spec_out, info, force)


def _publish(pack, folder, spec_out, info, force):
    spec_out['exec'] = _exec(info)
    dev._check_dest(folder, pack, force)
    path = dev._shown(folder / pack)
    files = _pack_files(pack, spec_out, info, path)
    dest = dev.publish(folder, pack, files, force)
    print('生了 %s/：1 支工具 %s（%d 個參數）' % (dest, pack.replace('-', '_'), len(spec_out['params'])))
    print('下一步：aos-agent tools test %s' % path)
    print('裝進家：aos-agent tools add %s --target 家' % path)
    return 0


# ------------------------------------------------------------------ 對照用：跟標準答案比 ----

def score(params, answer):
    """參數表 vs 標準答案（fixtures/wrapcli/answers.json 的一份）→ 找對、多抓、少抓、型別對、必填對、choices 對。
    選項用旗標有交集配對，位置參數用順序配對。"""
    pred_pos = [p for p in params if p['kind'] == 'positional']
    pred_opt = [p for p in params if p['kind'] != 'positional']
    ans_pos = [a for a in answer if not a['flags']]
    ans_opt = [a for a in answer if a['flags']]
    pairs = list(zip(pred_pos, ans_pos))
    used = set()
    for a in ans_opt:
        for i, p in enumerate(pred_opt):
            if i not in used and set(p['flags']) & set(a['flags']):
                used.add(i)
                pairs.append((p, a))
                break
    total_pred = len(params)

    def ptype(p):
        return ('integer' if p['kind'] == 'count' else p['type'], bool(p.get('array')))

    def same_choices(p, a):
        return sorted(map(str, p.get('choices') or [])) == sorted(map(str, a.get('choices') or []))

    return {'answer': len(answer), 'found': len(pairs), 'extra': total_pred - len(pairs),
            'missed': len(answer) - len(pairs),
            'type_ok': sum(ptype(p) == (a['type'], a['array']) for p, a in pairs),
            'required_ok': sum(bool(p.get('required')) == a['required'] for p, a in pairs),
            'choices_ok': sum(same_choices(p, a) for p, a in pairs)}
