import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
TOP = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(TOP / 'lib'), str(TOP / 'modules/tools')]
from aos7_fs import read_json, test_point, write_json
from aos7_taskside import task_env, wait_tock
MAIL = TOP / 'modules/mail/aos7-mail'
WF = TOP / 'modules/wfnode/aos7-wfnode'
CHECK_FIX = '跑 aos7-wfnode check <node> 看缺哪個'
AI_FIX = '等一下再 ask 一次；一直這樣就看 aos7-up status 的 AI 那行'
def trouble(why, fix):
    return why + '。怎麼辦：' + fix
class Trouble(ValueError):
    def __init__(self, why, fix):
        self.why, self.fix = why, fix
        super().__init__(trouble(why, fix))
class Later(Exception):
    """同一封信與同一筆 AI 請求留到下一次處理。"""


class AIReply(str):
    def __new__(cls, text, usage_pending=False):
        reply = super().__new__(cls, text)
        reply.usage_pending = usage_pending
        return reply


def run(tool, *args, node=None, timeout=30, env=None):
    return subprocess.run([sys.executable, str(tool), *map(str, args)], cwd=node,
                          env=env, capture_output=True, text=True, timeout=timeout)
def checked(tool, *args, **kwargs):
    p = run(tool, *args, **kwargs)
    if p.returncode:
        raise Trouble('工具沒完成', CHECK_FIX)
    return p.stdout
def mail(node, *args):
    return checked(MAIL, *args, '--root', node.parent, node=node)
def is_fake(cfg):
    return cfg.get('model') in (None, 'fake', '')
def cid_of(ident):
    cid = re.sub(r'[^A-Za-z0-9_-]', '-', ident)
    return cid if len(cid) <= 64 else cid[:47] + '-' + hashlib.sha1(ident.encode()).hexdigest()[:16]
def flat(text):
    return ' '.join(text.split())
def parse(text, ident):
    match = re.search(r'回信：(.*?)停在哪：([^\n]*)', text, re.S)
    reply, line = (match[1].strip(), flat(match[2])) if match else (text.strip(), '回了 ' + ident)
    title = next((re.sub(r'^[\s#>*_`-]+', '', s).strip() for s in reply.splitlines() if s.strip()), '已回信')
    return reply, flat(title)[:80] or '已回信', line or '回了 ' + ident
def fifo(letter):
    at = datetime.datetime.fromisoformat(letter['at']).timestamp()
    stamp = re.search(r'(\d{8}T\d{6})', letter['id'])
    seq = re.match(r'\d{8}T\d{4}(?:_(\d+))?-', Path(letter['file']).name)
    return at, stamp[1] if stamp else '', int(seq[1] or 0) if seq else 0, Path(letter['file']).name
def request(node, letter, cid, cfg):
    work = node / 'brain'
    req = work / 'req.json'
    saved = node / 'llmcall' / Path(cfg.get('budget', 'budget/llm')).name / cid / 'request.json'
    if saved.exists():
        write_json(str(req), json.loads(saved.read_text())['request'])
        return req
    try:
        skills = read_json(str(node / 'skills/index.json'), {}) or {}
        lines = [f"{n}：{flat(v['description'])}" for n, v in skills.get('skills', {}).items()]
        (work / 'now.md').write_text('技能：\n' + ('\n'.join(lines) or '（還沒有技能）') +
                                    '\n\n收到的信：\n' + Path(letter['file']).read_text(), encoding='utf-8')
        checked(TOP / 'packs/prompt/bin/aos7-prompt', 'render', node,
                TOP / 'modules/up/prompts/brain.json', '--out', req, node=node)
        obj = json.loads(req.read_text())
    except Exception:
        raise Trouble('讀不到工作簿的檔', CHECK_FIX) from None
    if is_fake(cfg):
        chars = sum(len(m['content']) for m in obj['litellm']['messages'])
        obj = {'fake': dict(mode='ok', usage=chars // 3 + 20,
                           text='回信：（假 AI）收到你的信：' + flat(letter['title']) + '\n停在哪：回了 ' + letter['id'])}
    else:
        obj['litellm']['model'] = cfg['model']
    write_json(str(req), obj)
    return req
def ask_ai(node, letter, cid, cfg):
    req = request(node, letter, cid, cfg)
    deadline = cfg.get('deadline', 60 if is_fake(cfg) else 600)
    env = os.environ.copy()
    env.pop('AOS7_LITELLM_URL', None)
    if not is_fake(cfg) and cfg.get('litellm_url'):
        env['AOS7_LITELLM_URL'] = cfg['litellm_url']
    try:
        p = run(TOP / 'packs/llmcall/bin/aos7-llmcall', 'call', cfg.get('budget', 'budget/llm'),
                '--holder', cfg.get('holder', 'brain'), '--call', cid, '--logical', 'up/brain',
                '--request', req, '--reserve', cfg.get('reserve', 1000000), '--deadline', deadline,
                node=node, env=env, timeout=float(deadline) + 15)
        if p.returncode == 3:
            raise Later()
        if p.returncode not in (0, 4):
            raise ValueError()
        receipt = json.loads(p.stdout.splitlines()[-1])
        text = receipt.get('text')
        if not isinstance(text, str) or not text.strip():
            raise ValueError()
    except Later:
        raise
    except Exception:
        raise Trouble('AI 沒回應', AI_FIX) from None
    test_point('up-brain-after-llm')
    return AIReply(text, usage_pending=p.returncode == 4)
def state_count(node, line):
    return sum(s.endswith(' ' + line) for p in (node / 'wf/handoffs').glob('*/STATE.md')
               for s in p.read_text().splitlines())
def finish(node, pending, personal):
    if any(l['id'] == pending['id'] for l in personal):
        body = node / 'brain/reply.md'
        body.write_text(pending['body'] + '\n', encoding='utf-8')
        mail(node, 'done', node.name, pending['id'], pending['status'], pending['title'], body)
    test_point('up-brain-after-mail')
    if state_count(node, pending['line']) <= pending['state_count']:
        checked(WF, 'state', node, pending['line'], node=node)
    test_point('up-brain-after-state')
    (node / 'brain/pending.json').unlink()
def once(node, rnd):
    work = node / 'brain'
    work.mkdir(exist_ok=True)
    personal = [l for l in json.loads(mail(node, 'read', node.name, '--json')) if l.get('type') == 'mail']
    pending = read_json(str(work / 'pending.json'))
    if pending:
        finish(node, pending, personal)
        if pending['status'] == 'BLOCKED':
            print(f'回合 {rnd}：' + trouble(pending['line'], pending['body'].split('怎麼辦：')[-1]), flush=True)
        elif pending.get('usage_pending'):
            print(f'回合 {rnd}：已回信（AI 用量還沒對清，之後自己會對）', flush=True)
        return
    requests = []
    for letter in personal:
        if letter['status'] == 'REQUEST':
            requests.append(letter)
        else:
            mail(node, 'done', node.name, letter['id'])
    if not requests: return
    letter = min(requests, key=fifo)
    ident, status, fix = letter['id'], 'DONE', ''
    usage_pending = False
    try:
        try:
            cfg = json.loads((node / '.aos/up.json').read_text()) if (node / '.aos/up.json').exists() else {}
            if not isinstance(cfg, dict):
                raise ValueError()
        except Exception:
            raise Trouble('設定檔 .aos/up.json 壞了', '刪掉它再跑 aos7-up <node>') from None
        text = ask_ai(node, letter, cid_of(ident), cfg)
        reply, title, line = parse(text, ident)
        usage_pending = getattr(text, 'usage_pending', False)
    except Later:
        print(f'回合 {rnd}：AI 還沒確定回沒回，下回合再看同一筆', flush=True)
        return
    except Exception as e:
        status = 'BLOCKED'
        title, fix = (e.why, e.fix) if isinstance(e, Trouble) else ('讀寫沒完成', CHECK_FIX)
        reply, line = '原因：' + title + '\n怎麼辦：' + fix, '卡住：' + title
    pending = dict(id=ident, status=status, title=title, body=reply, line=line, state_count=state_count(node, line), usage_pending=usage_pending)
    write_json(str(work / 'pending.json'), pending)
    test_point('up-brain-after-pending')
    finish(node, pending, personal)
    note = '已回信（AI 用量還沒對清，之後自己會對）' if usage_pending else '已回信'
    print(f'回合 {rnd}：' + (trouble(line, fix) if fix else note), flush=True)
def main(argv=None):
    from aos7_up_cli import Parser, show_help
    argv = sys.argv[1:] if argv is None else argv
    if show_help(argv):
        return 0
    if argv and argv[0] == 'ask':
        from aos7_up_ask import main as ask_main
        return ask_main(argv)
    ap = Parser(command='brain')
    ap.add_argument('cmd', choices=['brain'])
    ap.add_argument('node')
    a = ap.parse_args(argv)
    try:
        node = Path(a.node).resolve()
        env = task_env()
        last = 0
        while True:
            last = wait_tock(env['task'], last, run=env['run'])
            try:
                once(node, last)
            except Exception:
                print(f'回合 {last}：卡住：' + trouble('收尾沒完成', CHECK_FIX), flush=True)
    except (KeyError, ValueError):
        print('aos7-up: brain 只能由心跳起。用 aos7-up <node> 起 node', file=sys.stderr)
        return 2
    except OSError:
        print('aos7-up: 不確定：brain 讀寫故障。照原樣再跑 aos7-up <node> 會接續', file=sys.stderr)
        return 3
if __name__ == '__main__':
    sys.exit(main())
