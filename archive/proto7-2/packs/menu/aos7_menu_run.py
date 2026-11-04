"""選單驅動：先存意圖，再問一次或做一件事。"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from aos7_menu_io import (PACK, Stop, action, ai, event, read, safe_path, save)
from aos7_fs import N, OK, LockTimeout, Unknown, fact, locked, test_point
from aos7_menu import MenuError, after, load, new_state, render, step, view
from aos7_menu_check import template, validate_brief, BriefError
from aos7_menu_state import valid_state, pending_ok

def state_error(directory):
    return Stop(3, f'不確定：{directory.name} 的 state.json 讀不出來（原檔留著）。要接續就把它修回合法 JSON；要放棄就刪掉 {directory}/ 或換 --run 重走')

def summary(menu, state):
    label = f"選單 {state['run']}："
    if state['status'] == 'done':
        return label + '做完' + ('，寫了 ' + '、'.join('out/' + p for p in state['done']) if state['done'] else '')
    if state['status'] == 'stuck':
        return label + '停下——' + str(state['why'])
    ask = menu['layers'][state['layer']].get('ask', state['layer'])
    return label + f"走到「{template(ask, state['vars'])}」（第 {state['step']} 步，這層重問 {state['tries']} 次）"

def prompt(menu, state, directory):
    shown = None
    show = menu['layers'][state['layer']].get('show')
    if show:
        try:
            path = safe_path(directory, template(show, state['vars']))
            if path.exists():
                if path.stat().st_size > 8192:
                    raise MenuError('檔超過 8192 bytes。縮短內容再跑')
                shown = path.read_text(encoding='utf-8')
        except MenuError as e:
            raise MenuError(f"層 {state['layer']} 的欄位 show：{e}") from None
    return render(menu, state, shown=shown)

def stop_state(state, why, code=1):
    state.update(status='stuck', why=why, code=code, pending=None)
    event(state, 'stuck', state['layer'], rc=code, why=why)

def drive(node, path, menu, tools, directory, state, args):
    manual = Path(args.reply).read_text(encoding='utf-8') if args.reply else None
    taken = False
    save(directory, state)
    while True:
        nxt = view(menu, state)
        kind = nxt['kind']
        if kind == 'done':
            if not state.get('journal') or state['journal'][-1]['kind'] != 'done':
                state['status'] = 'done'
                event(state, 'done', state['layer'])
                save(directory, state)
            print(summary(menu, state))
            return 0
        if kind == 'stuck':
            if state['status'] != 'stuck':
                stop_state(state, nxt['why'], nxt.get('code', 1))
                save(directory, state)
            raise Stop(nxt.get('code', 1), nxt['why'])
        layer = state['layer']
        if kind == 'ask':
            text = prompt(menu, state, directory)
            if manual is not None and taken:
                print(text)
                return 0
            if not state['pending']:
                state['pending'] = {k: nxt[k] for k in ('call_id', 'layer')}
                event(state, 'ask', layer, call_id=nxt['call_id'], prompt_chars=len(text))
                save(directory, state)
            test_point('menu-pending')
            call_id = state['pending']['call_id']
            try:
                received = state['pending'].get('received')
                if received is not None:
                    reply, used, rc = (received[k] for k in ('reply', 'used', 'rc'))
                else:
                    reply, used, rc = (manual, 0, 0) if manual is not None else ai(node, directory, path, state, text, args.llm)
                args.unsettled = args.unsettled or rc == 4
            except Stop as e:
                if e.code == 1 and e.keep:
                    stop_state(state, e.why)
                    save(directory, state)
                raise
            test_point('menu-ai')
            base = copy.deepcopy(state)
            base['pending'] = None
            base['calls'].append(dict(layer=layer, call_id=call_id, rc=rc, used=used))
            try:
                state, nxt = step(menu, base, reply)
            except (MenuError, OSError, ValueError, KeyError, TypeError) as e:
                state['pending']['received'] = dict(reply=reply, used=used, rc=rc)
                event(state, 'reply-error', layer, call_id=call_id, reply_chars=len(reply),
                      used=used, rc=rc, unsettled=rc == 4, why=str(e))
                save(directory, state)
                raise
            event(state, 'exit' if state['status'] == 'stuck' and not state['tries'] else
                  'bad' if state['tries'] else 'pick', layer, call_id=call_id, prompt_chars=len(text),
                  reply_chars=len(reply), used=used, rc=rc, why=state.get('why'), fence=state.get('fence', False),
                  **({'unsettled': True} if rc == 4 else {}))
            save(directory, state)
            taken = True
        else:
            act = nxt['act']
            if not state['pending']:
                state['pending'] = {'act': act}
                save(directory, state)
            result = action(node, directory, act, tools)
            test_point('menu-act')
            test_point('menu-act:' + layer)
            state, nxt = after(menu, state, result)
            event(state, 'write' if 'write' in act else 'tool', layer, rc=result.get('rc', 0), why=result.get('err'))
            save(directory, state)

def run(args):
    node, path = Path(args.node).resolve(), Path(args.menu).resolve()
    if not node.is_dir():
        raise MenuError('node 不在。給存在的資料夾，例如 ~/my-node')
    tools = read(Path(os.environ.get('AOS7_MENU_TOOLS', PACK / 'tools.json')))
    menu = load(read(path), tools)
    name = args.run or menu['name']
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', name):
        raise MenuError('--run 名字不合。給 1～40 個英數、底線或減號，例如 hello-1')
    values = {}
    for pair in args.var:
        k, sep, v = pair.partition('=')
        if not sep or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', k) or k in ('run', 'node', 'run_dir'):
            raise MenuError('--var 不合或用了內建變數。給例如 --var to=小明')
        values[k] = v
    brief = Path(args.brief).read_text(encoding='utf-8') if args.brief else ''
    validate_brief(menu, brief)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    directory = node / 'menu' / name
    directory.mkdir(parents=True, exist_ok=True)
    with locked(str(directory / 'state.json'), timeout=0):
        st, state = fact(str(directory / 'state.json'))
        if st == N:
            if (directory / 'log.jsonl').exists():
                raise Stop(3, '不確定：state.json 不見了，紀錄留著。請人看過再恢復 state.json')
            state = new_state(menu, name, dict(values, node=str(node), run_dir=str(directory)), brief, sha)
            state.update(menu=str(path), initial_vars=values, journal=[])
            # 先驗目前提示的模板，不把錯的首次呼叫存下來。
            if view(menu, state)['kind'] == 'ask':
                prompt(menu, state, directory)
        else:
            if st != OK or not isinstance(state, dict):
                raise state_error(directory)
            if not all(isinstance(state.get(k), str) for k in ('menu', 'menu_sha')):
                raise state_error(directory)
            if state['menu_sha'] != sha or state['menu'] != str(path):
                raise MenuError('這個 run 用的選單改過了。改回原樣，或換 --run 重走')
            try:
                valid = valid_state(state, menu) and state['run'] == directory.name and state['vars']['node'] == str(node)
            except MenuError:
                valid = False
            if not valid:
                raise state_error(directory)
            if any(state.get('initial_vars', {}).get(k) != v for k, v in values.items()) or args.brief and brief != state['brief']:
                raise MenuError('接續的變數或摘要跟第一次不同。給原值，或換 --run 重走')
        if st == OK and state['status'] == 'walking':
            try:
                nxt = view(menu, state)
                if nxt['kind'] == 'ask':
                    prompt(menu, state, directory)
            except BriefError:
                raise
            except MenuError:
                raise state_error(directory) from None
        return drive(node, path, menu, tools, directory, state, args)

def status(args):
    node = Path(args.node).resolve()
    candidates = list((node / 'menu').glob('*/state.json'))
    if args.run:
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', args.run):
            raise MenuError('--run 名字不合。給例如 hello-1')
        path = node / 'menu' / args.run / 'state.json'
        if not path.exists():
            raise Stop(1, '沒有這個 run。先用 run 開一份選單')
    elif candidates:
        path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
    else:
        raise Stop(1, '沒有 run。先用 run 開一份選單')
    st, state = fact(str(path))
    if st != OK or not isinstance(state, dict):
        raise state_error(path.parent)
    try:
        tools = read(Path(os.environ.get('AOS7_MENU_TOOLS', PACK / 'tools.json')))
        menu = load(read(Path(state['menu'])), tools)
    except (KeyError, TypeError):
        raise state_error(path.parent) from None
    try:
        valid = valid_state(state, menu) and state['run'] == path.parent.name and state['vars']['node'] == str(node)
    except MenuError:
        valid = False
    if not valid:
        raise state_error(path.parent)
    try:
        if args.prompt and state['status'] == 'walking' and view(menu, state)['kind'] == 'ask':
            print(prompt(menu, state, path.parent))
        else:
            no_prompt = ''
            if args.prompt:
                if state['status'] == 'stuck':
                    no_prompt = '；這個 run 已停下，沒有正在等回答的提示'
                elif state['status'] == 'done':
                    no_prompt = '；這個 run 已做完，沒有正在等回答的提示'
                else:
                    no_prompt = '；目前正在做事，沒有正在等回答的提示'
            print(summary(menu, state) + no_prompt + (f'；另有 {len(candidates) - 1} 個 run' if not args.run and len(candidates) > 1 else ''))
    except BriefError:
        raise
    except MenuError:
        raise state_error(path.parent) from None
    return 0

def error(why):
    print('aos7-menu: ' + ' '.join(str(why).splitlines()), file=sys.stderr)

class Parser(argparse.ArgumentParser):
    def error(self, message):
        error(message + '。用法看 aos7-menu --help')
        self.exit(2)

def main(argv=None):
    ap = Parser(prog='aos7-menu', description='一次看一層選單，照編號走到寫檔或登記工具。')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('run', help='開始或接續選單')
    p.add_argument('node', help='已存在的工作資料夾，紀錄與輸出放在這裡。')
    p.add_argument('menu', help='要開始或接續的選單 JSON 檔。')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--llm', help='用這個模型回答，經工作資料夾的 budget/llm 帳呼叫。')
    group.add_argument('--reply', help='把這個檔案全文當回答走一步，再印下一層提示。')
    p.add_argument('--run', help='這次紀錄的名字，預設用選單 name；換名字可從頭重走。')
    p.add_argument('--var', action='append', default=[], help='填一個模板變數 K=V，可重複給。')
    p.add_argument('--brief', help='需求摘要；可用 === 段名 === 分段，由層 brief 選段，每步最多 1500 字。')
    p = sub.add_parser('status', help='看走到哪裡')
    p.add_argument('node', help='要查看紀錄的工作資料夾。')
    p.add_argument('--run', help='要查看的紀錄名字，預設看最近更新的 run。')
    p.add_argument('--prompt', action='store_true', help='印正在等回答的完整提示，沒有時說明原因。')
    args = ap.parse_args(argv)
    args.unsettled = False
    why = None
    try:
        return run(args) if args.cmd == 'run' else status(args)
    except MenuError as e:
        why = str(e)
        return 2
    except Stop as e:
        why = ('不確定：' if e.code == 3 and not str(e).startswith('不確定：') else '') + str(e)
        return e.code
    except LockTimeout:
        why = '另一個 aos7-menu 正在走這個 run。等它結束再跑'
        return 3
    except (OSError, Unknown, UnicodeError, KeyError, TypeError, ValueError) as e:
        why = f'不確定：執行沒能確認（{e}），state 與 pending 留著。照原樣再跑一次'
        return 3
    finally:
        if args.unsettled:
            why = (why + '；' if why else '') + '回答已收到，但帳還沒結清。查看 llmcall 的證據'
        if why:
            error(why)
