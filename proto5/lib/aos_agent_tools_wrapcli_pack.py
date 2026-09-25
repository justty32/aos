"""`tools wrap-cli` 產包：產的 run 程式樣板、工具描述、README、包內檔案，以及參數表印表。"""
import os

import aos_agent_tools_dev as dev

from aos_agent_tools_wrapcli_const import RUN_TIMEOUT


# ------------------------------------------------------------------ 產包 ----

WRAPCLI_RUN = r'''#!/usr/bin/env python3
"""aos-agent tools wrap-cli 產的 run：stdin 讀 arguments，照 wrapcli.json 的參數表驗型別、組 argv，
不經 shell 跑指令（cwd＝工作根目錄、stdin 關），回 stdout。
退出碼非 0＝CommandFailed（附 stderr 尾巴）；逾時＝Timeout（砍整個行程群組）。"""
import sys
sys.dont_write_bytecode = True
import json  # noqa: E402
import os  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
from _common import HERE, fail, run, truncate_tail  # noqa: E402

KIND = {'string': 'a string', 'integer': 'an integer', 'number': 'a number', 'boolean': 'a boolean'}
KEEP = 200 * 1024        # stdout、stderr 各只留最後這麼多位元組
STDERR_TAIL = 2000       # 錯誤 JSON 附的 stderr 尾巴（字元）
MAX_LINES = 2000
MAX_COUNT = 50


def spec():
    with open(os.path.join(HERE, 'wrapcli.json'), encoding='utf-8') as f:
        return json.load(f)


def check(value, p, where):
    t = p['type']
    ok = {'string': lambda v: isinstance(v, str),
          'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
          'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
          'boolean': lambda v: isinstance(v, bool)}[t](value)
    if not ok:
        fail('BadArguments', '%s must be %s' % (where, KIND[t]))
    if t == 'string' and '\0' in value:
        fail('BadArguments', '%s must not contain NUL' % where)
    if p.get('choices') and value not in p['choices']:
        fail('BadArguments', '%s must be one of %s' % (where, json.dumps(p['choices'], ensure_ascii=False)))
    return value


def text(v):
    return v if isinstance(v, str) else json.dumps(v)


def flag(p):
    longs = [f for f in p['flags'] if f.startswith('--')]
    return longs[0] if longs else p['flags'][0]


UNSAFE = 'value %r of argument "%s" starts with "-" and cannot be passed safely to this command (it would be read as a flag)'


def bind(p, value, mode):
    """帶值選項的一個值 → argv 片段。- 開頭的值：寫成 --opt=值 才不會被當成別的旗標，
    這要指令認得 = 寫法（argparse 的長旗標、help 寫了 --opt=）；做不到就 BadArguments。"""
    f = flag(p)
    if p.get('joiner') == '=':
        return [f + '=' + value]
    if value.startswith('-'):
        if f.startswith('--') and mode == 'argparse':
            return [f + '=' + value]
        fail('BadArguments', UNSAFE % (value, p['name']))
    return [f, value]


def build(info, args):
    """arguments → argv（不含指令本身）：開關、帶值選項照參數表順序，位置參數最後；
    位置參數有 - 開頭的值、或前面有「一個旗標接好幾個值」的選項（會把位置參數吃掉），就先放一個 --；
    nargs=* 明確給空陣列＝只給旗標（原程式拿到 []）；帶值選項的 - 開頭值見 bind()。"""
    known = {p['name'] for p in info['params']}
    extra = sorted(k for k in args if k not in known)
    if extra:
        fail('BadArguments', 'unknown argument(s): %s' % ', '.join(extra))
    argv, pos, greedy = [], [], False
    for p in info['params']:
        name = p['name']
        where = 'argument "%s"' % name
        value = args.get(name)
        if value is None:
            if p.get('required'):
                fail('BadArguments', 'missing required argument "%s"' % name)
            continue
        kind = p['kind']
        if kind == 'flag':
            if not isinstance(value, bool):
                fail('BadArguments', '%s must be a boolean' % where)
            if value:
                argv.append(flag(p))
            continue
        if kind == 'count':
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_COUNT:
                fail('BadArguments', '%s must be an integer 0..%d' % (where, MAX_COUNT))
            argv += [flag(p)] * value
            continue
        if p.get('array'):
            if not isinstance(value, list):
                fail('BadArguments', '%s must be an array' % where)
            values = [text(check(v, p, '%s[%d]' % (where, i))) for i, v in enumerate(value)]
            n = p.get('nargs')
            if isinstance(n, int) and len(values) != n:
                fail('BadArguments', '%s must have exactly %d items' % (where, n))
            if n == '+' and not values:
                fail('BadArguments', '%s must have at least 1 item' % where)
        else:
            values = [text(check(value, p, where))]
        if kind == 'positional':
            pos += values
        elif p.get('array') and p.get('multi') == 'once':
            for v in values:                          # 一個旗標接好幾個值：- 開頭的沒有安全寫法
                if v.startswith('-'):
                    fail('BadArguments', UNSAFE % (v, name))
            if values:
                argv += [flag(p)] + values
                greedy = True                         # 後面接位置參數的話要先放 --，免得被這個旗標吃掉（複審 M5）
            elif p.get('nargs') == '*':               # 明確給空陣列：旗標照給，原程式才拿到 []、不是 default
                argv.append(flag(p))
                greedy = True
        else:
            for v in values:
                argv += bind(p, v, info.get('mode'))
    if any(v.startswith("-") for v in pos) or (greedy and pos):
        argv.append('--')
    return argv + pos


class Tail:
    def __init__(self):
        self.buf, self.total = bytearray(), 0

    def drain(self, stream):
        try:
            for chunk in iter(lambda: stream.read1(65536), b''):
                self.total += len(chunk)
                self.buf += chunk
                if len(self.buf) > 2 * KEEP:
                    del self.buf[:-KEEP]
        except (OSError, ValueError):
            pass

    def text(self):
        return bytes(self.buf[-KEEP:]).decode('utf-8', 'replace')


def killpg(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def main(args, root):
    info = spec()
    argv = [os.path.join(HERE, a[1:]) if a.startswith('@') else a for a in info['exec']] + build(info, args)
    try:
        p = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    except OSError as e:
        fail('SpawnFailed', 'cannot start %s: %s' % (argv[0], e.strerror or e))
    signal.signal(signal.SIGTERM, lambda *_: (killpg(p.pid), os._exit(143)))
    out, err = Tail(), Tail()
    readers = [threading.Thread(target=t.drain, args=(s,), daemon=True) for t, s in ((out, p.stdout), (err, p.stderr))]
    for r in readers:
        r.start()
    limit = info.get('timeout', 50)
    timed_out = False
    try:
        code = p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        killpg(p.pid)
        code = p.wait()
    killpg(p.pid)                                         # 背景孩子一起收
    for r in readers:
        r.join(timeout=2)
    shown, cut = truncate_tail(out.text(), MAX_LINES)
    if cut or out.total > len(shown.encode('utf-8')):
        shown = '[output truncated: %d bytes total, showing only the end]\n' % out.total + shown
    tail = err.text()[-STDERR_TAIL:]
    if timed_out:
        fail('Timeout', 'command timed out after %d s and was killed' % limit, output=shown, timeout=limit,
             stderr=tail)
    if code != 0:
        fail('CommandFailed', 'command exited with code %d' % code, output=shown, exit_code=code, stderr=tail)
    if shown.strip():
        return shown
    return '(no output on stdout; stderr:)\n' + tail if tail.strip() else '(no output)'


if __name__ == '__main__':
    sys.exit(run(main))
'''


def _param_desc(p):
    where = ', '.join(p['flags']) if p['flags'] else '(positional)'
    text = '%s: %s' % (where, p['help']) if p.get('help') else where
    return text[:160]


def tool_entry(pack, spec):
    props, required = {}, []
    for p in spec['params']:
        if p['kind'] == 'flag':
            prop = {'type': 'boolean'}
        elif p['kind'] == 'count':
            prop = {'type': 'integer', 'minimum': 0}
        else:
            base = {'type': p['type']}
            if p.get('choices'):
                base['enum'] = list(p['choices'])
            prop = {'type': 'array', 'items': base} if p.get('array') else base
            if isinstance(p.get('nargs'), int):
                prop.update(minItems=p['nargs'], maxItems=p['nargs'])
            elif p.get('nargs') == '+':
                prop['minItems'] = 1
        prop['description'] = _param_desc(p)
        props[p['name']] = prop
        if p.get('required'):
            required.append(p['name'])
    params = {'type': 'object', 'properties': props}
    if required:
        params['required'] = required
    desc = (spec.get('description') or 'Run a command-line program.').rstrip()
    shown = os.path.basename(spec['command'])
    desc = '%s (runs `%s`; returns its stdout)' % (desc, shown)
    return {'type': 'function',
            'function': {'name': pack.replace('-', '_'), 'description': desc, 'parameters': params},
            '_meta': {'argv': ['tools/%s/run' % pack]}}


def _exec(info):
    if info['kind'] == 'path':
        return [info['name']]
    rel = '@src/' + info['path'].name
    return ['python3', rel] if info['py'] else [rel]


def _readme(pack, spec, path):
    lines = ['# %s — 從指令 `%s` 包出來的工具' % (pack, spec['command']), '',
             '`aos-agent tools wrap-cli` 產的（參數表來源：%s）。參數表在 `wrapcli.json`；'
             '要改參數表就改那個檔，再 `aos-agent tools wrap-cli %s --spec %s/wrapcli.json --force`。'
             % ({'mechanical': '機械解析', 'llm': '模型提案、人看過', 'spec': '人給的參數表'}.get(
                 spec['made_by'], spec['made_by']), spec['command'], path), '',
             '| 參數 | 旗標 | 型別 | 必填 | 說明 |', '|---|---|---|---|---|']
    for p in spec['params']:
        t = p['type'] + ('[]' if p.get('array') else '')
        if p.get('choices'):
            t += ' ∈ ' + '/'.join(map(str, p['choices']))
        lines.append('| `%s` | %s | %s | %s | %s |' % (p['name'], ', '.join(p['flags']) or '（位置）', t,
                                                        '是' if p.get('required') else '', p.get('help', '').replace('|', '\\|')))
    lines += ['', '## 怎麼跑', '',
              '`run`：stdin 讀 arguments JSON，照參數表驗型別（多給、少給必填、型別或 choices 不對＝`BadArguments`），'
              '組成 argv **不經 shell** 跑指令：開關給 true 才加、count 重複 N 次、帶值選項照參數表順序、位置參數最後'
              '（有 `-` 開頭的值先放 `--`）。cwd＝工作根目錄、stdin 關。回 stdout；退出碼非 0＝`CommandFailed`'
              '（stdout 原樣在前、JSON 帶 `exit_code` 與 `stderr` 尾巴）；%d 秒沒跑完＝`Timeout`（砍整個行程群組）。'
              % spec.get('timeout', RUN_TIMEOUT), '',
              '## 關牢', '',
              '工具檔沒寫 `_jail`＝預設關牢。指令在牢裡要找得到：PATH 上的指令來自主機唯讀掛進去的 `/usr`；'
              '檔案指令的副本在 `src/`（牢裡的 `/opt/tool/src/`）。指令碰得到的檔只有 `access.json` 掛進 `/work` 的資料夾。', '',
              '## 試、裝', '', '```sh', 'aos-agent tools test %s' % path, 'aos-agent tools add %s --target 家' % path,
              '```', '']
    return '\n'.join(lines)


def _pack_files(pack, spec, info, path):
    tools = [tool_entry(pack, spec)]
    files = [(pack + '.json', dev._dump(tools), False), ('run', WRAPCLI_RUN, True),
             ('wrapcli.json', dev._dump(spec), False), ('_common.py', dev.BASE_COMMON.read_bytes(), False),
             ('config.json', dev._dump({'root': 'workspace'}), False), ('README.md', _readme(pack, spec, path), False)]
    if info['kind'] == 'file':
        files.append(('src/' + info['path'].name, info['data'], not info['py']))
    return dev.package_files(pack, files)


# ------------------------------------------------------------------ 印表 ----

STATUS = {'ok': '收  ', 'reject': '拒收', 'skip': '不收'}


def _type_text(p):
    t = p['type'] + ('[]' if p.get('array') else '')
    if p['kind'] == 'count':
        t = 'count'
    if p.get('choices'):
        t += '∈{%s}' % ','.join(map(str, p['choices']))
    return t


def print_table(params, rows=None, unparsed=(), dropped=(), notes=()):
    """每個參數一行：收／拒收（原因）、從哪一行解出來。"""
    width = max([len(p['name']) for p in params] + [len(str(r[1])) for r in rows or []] + [6])
    for p in params:
        flags = ', '.join(p['flags']) or '（位置）'
        line = ('第 %d 行' % p['line']) if p.get('line') else ''
        print('收    %-*s  %-28s %-18s %s  %s' % (width, p['name'], flags, _type_text(p), '必填' if p.get('required')
                                                 else '選填', line))
    for status, label, why, line in rows or []:
        if status == 'ok':
            continue
        print('%s  %-*s  第 %s 行（%s）' % (STATUS[status], width, label, line, why))
    for label, why in dropped:
        print('丟掉  %s（%s）' % (label, why))
    for line, text, why in unparsed:
        print('解不出來：第 %d 行：%s（%s）' % (line, text[:80], why))
    for line, why in notes:
        print('附註：第 %d 行：%s' % (line, why))
