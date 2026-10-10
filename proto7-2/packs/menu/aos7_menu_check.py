"""選單的靜態驗證、模板與回法；只處理值，不碰檔案。"""
import copy
import posixpath
import re
import string

NAME = re.compile(r'^[A-Za-z0-9_-]{1,40}$')
BUILTINS = {'run', 'node', 'run_dir'}


class MenuError(ValueError):
    """選單或模板不合，呼叫端以退出碼 2 回報。"""
    code = 2


def require(ok, why):
    if not ok:
        raise MenuError(why + '。請改好選單再跑，例如參考 examples/hello/menu.json')


def keys(obj, allowed, label):
    require(isinstance(obj, dict), label + ' 要是物件')
    extra = set(obj) - set(allowed)
    require(not extra, label + ' 有不認得的欄位 ' + '、'.join(map(str, sorted(extra, key=str))))


def template(text, vars):
    require(isinstance(text, str), '模板要是字串')
    try:
        parts = []
        for literal, field, fmt, conv in string.Formatter().parse(text):
            parts.append(literal)
            if field is not None:
                require(bool(NAME.fullmatch(field)) and not fmt and not conv, '模板只收 {變數}')
                require(field in vars, '模板變數 ' + field + ' 不在，請用 --var ' + field + '=值')
                parts.append(str(vars[field]))
        return ''.join(parts)
    except ValueError as exc:
        if isinstance(exc, MenuError):
            raise
        raise MenuError('模板括號不成對。字面括號請寫 {{ 或 }}') from exc


def normalize_out(path):
    require(isinstance(path, str) and path and not path.startswith('/') and
            '\\' not in path and '..' not in path.split('/'),
            '路徑要相對 out/，不能有 .. 或絕對路徑')
    path = posixpath.normpath(path)
    path = path.removeprefix('out/')
    require(path not in ('.', 'out', ''), '路徑要有檔名，例如 out/reply.txt')
    return path


def out_path(text, vars):
    return 'out/' + normalize_out(template(text, vars))


def at(label, fn, *args):
    try:
        return fn(*args)
    except MenuError as exc:
        raise MenuError(label + '：' + str(exc)) from None


def validate(obj, tools):
    keys(obj, ('v', 'name', 'start', 'required', 'layers'), '選單')
    require(type(obj.get('v')) is int and obj['v'] == 1, '選單 v 要是 1')
    require(isinstance(obj.get('name'), str) and bool(NAME.fullmatch(obj['name'])), '選單 name 要是 1～40 個英數、底線或短橫')
    layers = obj.get('layers')
    require(isinstance(layers, dict) and bool(layers), 'layers 要是非空物件')
    require(isinstance(obj.get('required', []), list) and all(isinstance(p, str) for p in obj.get('required', [])), 'required 要是檔名清單')
    keys(tools, ('v', 'tools'), '工具目錄')
    require(tools.get('v') == 1 and isinstance(tools.get('tools'), dict), '工具目錄要有 v:1 與 tools 物件')
    registry = tools['tools']
    for name, entry in registry.items():
        keys(entry, ('about', 'argv', 'args', 'out', 'timeout'), '工具 ' + str(name))
        require(isinstance(entry.get('argv'), list) and bool(entry['argv']) and all(isinstance(x, str) for x in entry['argv']), '工具 argv 要是非空字串清單')
        require(isinstance(entry.get('args'), list) and all(isinstance(x, str) and NAME.fullmatch(x) for x in entry['args']) and len(set(entry['args'])) == len(entry['args']), '工具 args 要是參數名字清單')
        require(entry.get('out') in ('code', 'json-line'), '工具 out 要是 code 或 json-line')
        require(type(entry.get('timeout', 300)) in (int, float) and entry.get('timeout', 300) > 0, '工具 timeout 要是正數')
        for arg in entry['argv']:
            template(arg, dict.fromkeys(entry['args'] + ['py', 'top', 'pack', 'node', 'run_dir'], ''))
    def target(value, label='start'):
        require(isinstance(value, str) and (value == 'end' or value in layers), label + ' 指不到層')
    def tool(name, args):
        require(isinstance(name, str) and name in registry, '工具沒登記：' + str(name))
        require(isinstance(args, dict) and set(args) == set(registry[name].get('args', [])), '工具 ' + name + ' 的參數鍵與登記不一致')
        require(all(isinstance(v, str) for v in args.values()), '工具參數要是模板字串')
    target(obj.get('start'))
    for name, layer in layers.items():
        require(isinstance(name, str) and bool(NAME.fullmatch(name)), '層名要是 1～40 個英數、底線或短橫')
        try:
            keys(layer, ('ask', 'options', 'exit', 'slot', 'do', 'next', 'show', 'ok', 'fail', 'max_rounds'), '層 ' + name)
            for key in ('next', 'ok', 'fail'):
                if key in layer:
                    target(layer[key], key)
            if 'show' in layer:
                require(isinstance(layer['show'], str) and layer['show'].startswith('out/'), 'show 要是 out/ 路徑')
            if 'max_rounds' in layer:
                require(type(layer['max_rounds']) is int and layer['max_rounds'] > 0, 'max_rounds 要是正整數')
            if 'slot' in layer:
                slot = layer['slot']
                keys(slot, ('max_bytes', 'max_lines', 'prefix', 'sections', 'tool'), 'slot')
                for key in ('max_bytes', 'max_lines'):
                    if key in slot:
                        require(type(slot[key]) is int and slot[key] > 0, key + ' 要是正整數')
                require('prefix' not in slot or isinstance(slot['prefix'], str), 'prefix 要是字串')
                require('sections' not in slot or (isinstance(slot['sections'], list) and all(isinstance(x, str) for x in slot['sections'])), 'sections 要是字串清單')
                if 'tool' in slot:
                    at('slot.tool', tool, slot['tool'], {'path': ''})
            if 'do' in layer:
                do = layer['do']
                require(isinstance(do, dict), 'do 要是物件')
                if 'write' in do:
                    keys(do, ('write',), 'do.write')
                    require(isinstance(do['write'], str) and 'ask' in layer and 'slot' in layer, 'write 要有 ask／slot，路徑例如 out/reply.txt')
                else:
                    keys(do, ('tool', 'args'), 'do')
                    at('do.tool／args', tool, do.get('tool'), do.get('args', {}))
            if 'ask' in layer:
                require(isinstance(layer['ask'], str), 'ask 要是字串')
                require('exit' in layer, '缺出口 exit。每個問的層都要有，例 \"exit\": {\"text\": \"都不是，要你決定\"}')
                keys(layer.get('exit'), ('text',), 'exit')
                require(isinstance(layer['exit'].get('text'), str), 'exit 要有 text')
                options = layer.get('options')
                if isinstance(options, dict):
                    keys(options, ('from', 'only'), 'options')
                    require(options.get('from') == 'done', 'options.from 只收 done')
                    require('only' not in options or (isinstance(options['only'], list) and all(isinstance(x, str) for x in options['only'])), 'options.only 要是模板字串清單')
                    require('next' in layer, '動態 options 要有 next')
                else:
                    require(isinstance(options, list) or (options is None and 'slot' in layer), 'options 要是清單，或改用 slot')
                    if options is None:
                        require('next' in layer, 'slot 層要有 next')
                    for option in options or []:
                        keys(option, ('text', 'next', 'set', 'when'), 'options')
                        require(isinstance(option.get('text'), str), 'options.text 要是字串')
                        target(option.get('next'), 'options.next')
                        values = option.get('set', {})
                        require(isinstance(values, dict) and all(isinstance(k, str) and NAME.fullmatch(k) and k not in BUILTINS and isinstance(v, str) for k, v in values.items()), 'options.set 要是變數到模板，不能蓋內建變數')
                        when = option.get('when')
                        require(when is None or (isinstance(when, str) and (when in ('required_done', 'required_missing') or when.startswith('new:'))), 'options.when 只收 required_done、required_missing、new:路徑')
                    if not any('when' in x for x in options or []):
                        require(2 <= (len(options) if options is not None else 1) + 1 <= 5, 'options 含出口要 2～5 個')
            else:
                require('do' in layer and 'tool' in layer['do'] and 'ok' in layer, '做事層要有 do.tool 與 ok')
        except MenuError as exc:
            raise MenuError('層 ' + name + ' ' + str(exc)) from None
    return copy.deepcopy(obj)


def parse_reply(reply, slot=False):
    lines = reply.splitlines(keepends=True)
    while lines and not lines[0].strip():
        lines.pop(0)
    match = re.fullmatch(r'選\s*[:：]\s*([0-9０-９]+)', lines[0].strip()) if lines else None
    if not match:
        return None, None, False, '第一行要回 選：編號'
    number = int(match[1])
    if not slot:
        return number, None, False, None
    if len(lines) < 2 or not re.match(r'^格[:：]', lines[1]):
        return number, None, False, '下一行要有 格：內容'
    text = re.sub(r'^格[:：]', '', lines[1], count=1)
    if not text.strip():
        text = ''
    text += ''.join(lines[2:])
    text = text.rstrip() + '\n'
    fence = re.fullmatch(r'```[^\n]*\n(.*?)\n```\n', text, re.S)
    if fence:
        text = fence[1].rstrip() + '\n'
    return number, text, bool(fence), None


def expanded_slot(slot, vars):
    slot = copy.deepcopy(slot)
    if 'prefix' in slot:
        slot['prefix'] = at('prefix', template, slot['prefix'], vars)
    if 'sections' in slot:
        slot['sections'] = [at('sections', template, x, vars) for x in slot['sections']]
    return slot


def check_slot(slot, text, vars=None):
    slot = expanded_slot(slot, vars or {})
    if not text.strip():
        return '格子是空的'
    if 'max_bytes' in slot and len(text.encode('utf-8')) > slot['max_bytes']:
        return '格子超過 max_bytes'
    lines = text.splitlines()
    if 'max_lines' in slot and len(lines) > slot['max_lines']:
        return '格子超過 max_lines'
    if 'prefix' in slot and not lines[0].startswith(slot['prefix']):
        return '第一行要以 ' + slot['prefix'] + ' 開頭'
    if any(not any(line.startswith(s) for line in lines) for s in slot.get('sections', [])):
        return '缺少 sections 要的段落'
    return None
