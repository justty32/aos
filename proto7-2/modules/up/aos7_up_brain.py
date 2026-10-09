import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shlex
import time
import sys
TOP = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent), str(TOP / 'lib'), str(TOP / 'modules/tools')]
import aos7_up_memory as memory
_PICKED = {}
from aos7_fs import BAD, N, OK, fact, read_json, test_point, write_json
from aos7_taskside import task_env, wait_tock
MAIL = TOP / 'modules/mail/aos7-mail'
WF = TOP / 'modules/wfnode/aos7-wfnode'
CHECK_FIX = '跑 aos7-wfnode check <node> 看缺哪個'
LAST_MAX = 4000
AI_FIX = '等一下再 ask 一次；一直這樣就看 aos7-up status 的 AI 那行'
def trouble(why, fix):
    return why + '。怎麼辦：' + fix
class Trouble(ValueError):
    def __init__(self, why, fix):
        self.why, self.fix = why, fix
        super().__init__(trouble(why, fix))
class Later(Exception):
    """同一封信與同一筆 AI 請求留到下一次處理。"""
    def __init__(self, unsure=True):
        self.unsure = unsure


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
def ai_deadline(cfg):
    return float(cfg.get('deadline', 60 if is_fake(cfg) else 600))
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
def task_of(node):
    """讀不到（I/O）丟 OSError＝這回合不動；壞掉的 task.json 刪掉，從第 1 回合重播（llmcall 回條重用，不重問）。"""
    path = node / 'brain/task.json'
    st, task = fact(str(path))
    if st == N:
        return None
    keys = dict(id=str, step=int, line=str, stall=int, trail=list)
    if st == OK and isinstance(task, dict) and all(isinstance(task.get(k), t) for k, t in keys.items()):
        return task
    if st == BAD or st == OK:
        path.unlink(missing_ok=True)
        return None
    raise OSError(task)
def step_of(node, letter):
    task = task_of(node)
    return task if task and task.get('id') == letter['id'] else None
def call_id(ident, step):
    return cid_of(ident if step == 1 else f'{ident}-s{step}')
def pick_skill(node, title):
    """本機關鍵字挑技能：經 brain/.pick 視角呼叫 aos7-skills pick（視角沒有帳，所以不問 AI）。"""
    if not (node / 'skills').is_dir():
        return None
    view = node / 'brain/.pick'
    view.mkdir(exist_ok=True)
    link = view / 'skills'
    try:
        if not link.is_symlink():
            link.symlink_to(node / 'skills')
        p = run(TOP / 'modules/skills/aos7-skills', 'pick', view, flat(title), node=node)
        found = Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
        return found.parent.name if found else None
    finally:
        link.unlink(missing_ok=True)
        view.rmdir()
def skill_of(node, letter):
    key = (str(node), letter['id'])
    if key not in _PICKED:
        _PICKED[key] = pick_skill(node, letter['title'])
    return _PICKED[key]
def fake_text(letter, step, ref=None, got=None, latest=None):
    title = flat(letter['title'])
    want = re.search(r'(\d+)\s*回合', title)
    if '要你決定' in title:
        return f'要你決定：（假 AI）缺資料，請補上\n停在哪：第 {step} 回合等你'
    if '沒進展' in title:
        return f'繼續：（假 AI）第 {step} 回合還是卡住\n停在哪：卡在同一處'
    if want and step < int(want[1]):
        return f'繼續：（假 AI）第 {step} 回合做完\n停在哪：第 {step} 回合，下一步第 {step + 1} 回合'
    if '要檔案' in title and ref is None and latest:
        return '要檔案：' + latest
    attached = f'（附了前件 {ref}）' if got is not None else ''
    return '回信：（假 AI）收到你的信：' + title + attached + '\n停在哪：回了 ' + letter['id']
def request(node, letter, cid, cfg):
    work = node / 'brain'
    req = work / 'req.json'
    saved = node / 'llmcall' / Path(cfg.get('budget', 'budget/llm')).name / cid / 'request.json'
    if saved.exists():
        write_json(str(req), json.loads(saved.read_text())['request'])
        return req
    task = step_of(node, letter)
    step = task['step'] if task else 1
    try:
        skills = read_json(str(node / 'skills/index.json'), {}) or {}
        lines = [f"{n}：{flat(v['description'])}" for n, v in skills.get('skills', {}).items()]
        skills_text = '技能：\n' + ('\n'.join(lines) or '（還沒有技能）') + '\n\n'
        skill = task.get('skill') if task else skill_of(node, letter)
        parts = dict(skill='', trail='', attach='', state=memory.state_text(node))
        if skill and (node / 'skills' / skill / 'SKILL.md').is_file():
            parts['skill'] = f'挑到的技能 {skill}：\n' + (node / 'skills' / skill / 'SKILL.md').read_text()[:3000] + '\n\n'
        letter_text = Path(letter['file']).read_text()
        ref = memory.wanted(task) if task else None
        if ref is None:
            ref = memory.pick(node, letter['title'] + '\n' + letter_text)
        got = memory.attach(node, ref) if ref else None
        index = memory.section(node, None, None)
        parts['attach'] = memory.section(node, ref, got)[len(index):]
        if task:
            parts['trail'] = f"這是第 {step} 回合（最多 {cfg.get('max_steps', 40)}）。前幾回合（最近 8 回合）：\n" + '\n'.join(task['trail']) + '\n\n'
        def render():
            (work / 'now.md').write_text(skills_text + parts['skill'] + index + parts['attach'] + parts['state'] + parts['trail'] +
                                        '收到的信：\n' + letter_text, encoding='utf-8')
            checked(TOP / 'packs/prompt/bin/aos7-prompt', 'render', node, TOP / 'modules/up/prompts/brain.json',
                    '--out', req, node=node)
            return json.loads(req.read_text())
        def size(obj):
            return sum(len(m['content']) for m in obj['litellm']['messages'])
        if not task:
            (work / 'last.md').write_text('', encoding='utf-8')
        obj = render()
        limit = cfg.get('max_prompt_chars', memory.PROMPT_MAX)
        if size(obj) > limit:
            parts, _ = memory.fit(parts, size(obj), limit)
            obj = render()
            if size(obj) > limit:
                last = (work / 'last.md').read_text()
                keep = max(200, len(last) - (size(obj) - limit))
                write_text(work / 'last.md', last[:keep])
                obj = render()
    except Exception:
        raise Trouble('讀不到工作簿的檔', CHECK_FIX) from None
    if size(obj) > limit:
        raise Trouble(f'提示砍過還是超過 {limit} 字（信或工作簿太長）', '把信拆短再寄，或調大 .aos/up.json 的 max_prompt_chars')
    if is_fake(cfg):
        chars = sum(len(m['content']) for m in obj['litellm']['messages'])
        obj = {'fake': dict(mode='ok', usage=chars // 3 + 20, text=fake_text(letter, step, ref=ref, got=got,
                               latest=(memory.index_text(node).splitlines()[-1][2:].split('｜', 1)[0]
                                       if memory.index_text(node) else None)))}
        if cfg.get('fake_delay', 0) > 0:
            obj['fake'].update(mode='late', delay=cfg['fake_delay'])
    else:
        obj['litellm']['model'] = cfg['model']
    write_json(str(req), obj)
    return req
def ask_ai(node, letter, cid, cfg):
    req = request(node, letter, cid, cfg)
    deadline = ai_deadline(cfg)
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
            raw = node / 'llmcall' / Path(cfg.get('budget', 'budget/llm')).name / cid / 'raw.json'
            raise Later(unsure=not raw.exists())
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
    (node / 'brain/unsure.json').unlink(missing_ok=True)
    test_point('up-brain-after-llm')
    return AIReply(text, usage_pending=p.returncode == 4)
def state_count(node, line):
    return sum(s.endswith(' ' + line) for p in (node / 'wf/handoffs').glob('*/STATE.md')
               for s in p.read_text().splitlines())
def state_once(node, key, line, before=None):
    path = node / 'brain/state.json'
    st, saved = fact(str(path))
    if (st != OK or not isinstance(saved, dict) or not isinstance(saved.get('done'), list)
            or not all(isinstance(k, str) for k in saved['done'])
            or (saved.get('doing') is not None and
                (not isinstance(saved['doing'], dict) or not isinstance(saved['doing'].get('key'), str)
                 or not isinstance(saved['doing'].get('count'), int)))):
        saved = dict(done=[], doing=None)
    if key in saved['done']:
        return
    doing = saved.get('doing')
    if doing and doing['key'] == key:
        before = doing['count']
    elif before is None:
        before = state_count(node, line)
    saved['doing'] = dict(key=key, count=before)
    write_json(str(path), saved)
    if state_count(node, line) <= before:
        checked(WF, 'state', node, line, node=node)
    saved.update(done=(saved['done'] + [key])[-50:], doing=None)
    write_json(str(path), saved)
def locked(node, edit):
    """跟 compact 共用 write.lock 改記憶檔（compact spec 的合作追加者）。"""
    (node / 'compact').mkdir(exist_ok=True)
    with open(node / 'compact/write.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        edit()
def open_line(node, ident, line=None):
    """SESSION-LOG 第一段裡這封信的 open 一行：給 line 就寫（換掉舊的），不給就刪；ident 為 None＝刪掉全部 brain 行。"""
    if line:
        line = line.replace('已完成', '已做好').replace('已結案', '已收').replace('已收線', '已收')
        line = re.sub(r'（完成）|✅|✔|~~', '', line)
        line = re.sub(r'DONE|\(done\)|\[done\]', 'done', line)
    path = node / 'wf/SESSION-LOG.md'
    mark = f'- [brain] 信 {ident}：' if ident else '- [brain] 信 '
    def edit():
        old = path.read_text().split('\n')
        rows = [r for r in old if not r.startswith(mark)]
        if line:
            at = next((k + 1 for k, r in enumerate(rows) if r.startswith('## ')), len(rows))
            rows.insert(at, mark + line)
        if rows != old:
            write_text(path, '\n'.join(rows))
    if path.exists() and (line or mark in path.read_text()):
        locked(node, edit)
def write_text(path, text):
    tmp = path.with_name(path.name + '.brain-tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)
def journal(node, ident, step, text):
    path = node / 'notes/journal.jsonl'
    def edit():
        path.parent.mkdir(exist_ok=True)
        old = path.read_text().splitlines()[-20:] if path.exists() else []
        key = json.dumps(dict(by='brain', re=ident, step=step), ensure_ascii=False)[:-1]
        if not any(r.startswith(key) for r in old):
            with path.open('a', encoding='utf-8') as f:
                f.write(key + ', ' + json.dumps(dict(at=datetime.datetime.now().isoformat(timespec='seconds'),
                                                     text=text), ensure_ascii=False)[1:] + '\n')
    locked(node, edit)
def compact_if_big(node, cfg):
    if cfg.get('compact', True) is False:
        return False
    try:
        p = run(TOP / 'modules/compact/aos7-compact', 'now', node, node=node, timeout=float(cfg.get('deadline', 600)) + 30)
        if p.returncode:
            return False
        return any('job' in f for f in json.loads(p.stdout.splitlines()[-1])['files'])
    except Exception:
        return False
def progress(node, letter, step, title, body):
    """寄 PROGRESS 給寄件人；同一回合的 PROGRESS 已在對方信箱就不再寄。"""
    who = Path(letter.get('reply-to') or '').parent.name or letter['from']
    head = f'# 第 {step} 回合：'
    path = node / 'brain/progress.md'
    for p in (node.parent / who / 'inbox').rglob('*.md'):
        try:
            text = p.read_text(errors='replace')
        except FileNotFoundError:
            text = ''
        if f'\nre: {letter["id"]}\n' in text and '\nstatus: PROGRESS\n' in text and '\n' + head in text:
            path.unlink(missing_ok=True)
            return
    path.write_text(body + '\n', encoding='utf-8')
    mail(node, 'send', node.name, who, 'PROGRESS', head[2:] + title, path, '--re', letter['id'])
    path.unlink()
def drop_task(node, ident):
    open_line(node, ident)
    for name in ('task.json', 'last.md', 'progress.md', 'unsure.json'):
        (node / 'brain' / name).unlink(missing_ok=True)
def finish(node, pending, personal):
    if any(l['id'] == pending['id'] for l in personal):
        memory.record(node, pending['id'], pending.get('ask') or pending['title'], pending['status'], pending['body'])
        body = node / 'brain/reply.md'
        body.write_text(pending['body'] + '\n', encoding='utf-8')
        mail(node, 'done', node.name, pending['id'], pending['status'], pending['title'], body)
    test_point('up-brain-after-mail')
    state_once(node, f'{pending["id"]}#end', pending['line'], before=pending['state_count'])
    test_point('up-brain-after-state')
    drop_task(node, pending['id'])
    (node / 'brain/pending.json').unlink()
def kind_of(text):
    head = text.lstrip()
    return next((k for k in ('繼續：', '要你決定：', '要檔案：') if head.startswith(k)), '回信：')
def step_on(node, letter, text, cfg):
    """AI 說繼續：記這一回合（每項重跑不重做），最後才寫 task.json 進下一回合。回 (回合行, 卡住句) 或 None＝要停。"""
    task = step_of(node, letter) or dict(id=letter['id'], step=1, line='', stall=0, trail=[],
                                         skill=skill_of(node, letter))
    step = task['step']
    match = re.search(r'繼續：(.*?)停在哪：([^\n]*)', text, re.S)
    result, line = (match[1].strip(), flat(match[2])) if match else (text.strip()[len('繼續：'):].strip(), '')
    line = line or f'第 {step} 回合'
    stall = task['stall'] + 1 if line == task['line'] else 0
    if stall >= cfg.get('stall', 3):
        return None, f'連續 {stall} 回合沒進展，停在：{line}'
    if step >= cfg.get('max_steps', 40):
        return None, f'做了 {step} 回合還沒做完，停在：{line}'
    ident = letter['id']
    cut = result if len(result) <= LAST_MAX else result[:LAST_MAX] + f'\n（後面還有 {len(result) - LAST_MAX} 字沒附上）'
    (node / 'brain/last.md').write_text(f'上一回合（第 {step} 回合）的成果：\n{cut}\n', encoding='utf-8')
    journal(node, ident, step, line + '｜' + flat(result)[:300])
    state_once(node, f'{ident}#s{step}', f'第 {step} 回合 {ident}：{line}')
    open_line(node, ident, f'{line}（做完第 {step} 回合）→ 下回合接著做')
    every = cfg.get('progress_every', 5)
    if every and step % every == 0:
        progress(node, letter, step, line, result)
    test_point('up-brain-after-step')
    write_json(str(node / 'brain/task.json'), dict(task, step=step + 1, line=line, stall=stall,
               trail=(task['trail'] + [f'第 {step} 回合：{line}｜成果：{flat(result)[:200]}'])[-8:]))
    note = '，整理了記憶' if compact_if_big(node, cfg) else ''
    return f'第 {step} 回合做完，下回合接著做{note}', None
def minutes(seconds):
    """給人看的等待時間：一律說「約 N 分鐘」（不印秒數，免得跟範例對不上）。"""
    return f'約 {max(1, round(seconds / 60))} 分鐘'
def stuck_reply(node, cid, step, waited, cfg, ask=''):
    """回信只寫白話；給維護者的哪一筆、預留與放掉預留的一行，寫在 brain/stuck/<call>/how.md。
    brain 不替人重送或放掉預留。"""
    budget, holder = cfg.get('budget', 'budget/llm'), cfg.get('holder', 'brain')
    tool = TOP / 'packs/llmcall/bin/aos7-llmcall'
    def command(*args):
        return ' '.join(shlex.quote(str(a)) for a in ('python3', tool, *args))
    status_cmd = command('status', budget, '--holder', holder, '--call', cid)
    saved = read_json(str(node / 'llmcall' / Path(budget).name / cid / 'request.json'))
    reserve = '帳上沒有這筆的預留'
    how = ''
    status = None
    work = node / 'brain/stuck' / cid
    if saved:
        reserve = '預留多少不確定，跑 ' + status_cmd + ' 看'
        try:
            p = run(tool, 'status', budget, '--holder', holder, '--call', cid, node=node)
            got = json.loads(p.stdout)
            ledger = got['ledger']
            if p.returncode == 0 and 'error' not in ledger:
                status = got
                reserve = (f"帳上預留 {ledger['ledger']['amount']}" if ledger.get('stage') == 'reserved'
                           else '帳上沒有這筆的預留')
        except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
            pass
    if status and (status.get('gateway') or {}).get('stage') == 'intent':
        work.mkdir(parents=True, exist_ok=True)
        write_json(str(work / 'request.json'), saved['request'])
        write_json(str(work / 'reply.json'), dict(call_id=cid, req_sha=saved['req_sha'],
                   reply=dict(status='reject', billed=False, body='')))
        rel = 'brain/stuck/' + cid
        how += ('要放掉預留（心跳要開著）：在 node 資料夾裡跑這一行：\n' +
                'cd ' + shlex.quote(str(node)) + ' && ' +
                command('adopt', budget, '--holder', holder, '--call', cid, '--raw', rel + '/reply.json') + ' && ' +
                command('call', budget, '--holder', holder, '--call', cid, '--request', rel + '/request.json',
                        '--reserve', saved['reserve']) + '\n' +
                'reply.json 預設當作「這筆沒扣費」（記 0）。若從 LiteLLM 後台查到實際用量 N，' +
                '把 reply.json 裡的 reply 改成 {"status":"error","billed":true,"body":"","usage":{"total_tokens":N}} 再跑。\n' +
                '第二段退 1 是正常的（這筆記成沒答成），預留就放掉了。')
    elif status and status.get('gateway') is None and status['ledger'].get('stage') == 'reserved':
        budget_tool = TOP / 'packs/budget/bin/aos7-budget'
        def budget_command(op):
            return ' '.join(shlex.quote(str(a)) for a in
                            ('python3', budget_tool, op, budget, '--holder', holder, '--request', cid))
        how += ('這筆還沒送出給 AI。\n要放掉預留（心跳要開著）：在 node 資料夾裡跑這一行：\n' +
                'cd ' + shlex.quote(str(node)) + ' && ' + budget_command('cancel') + ' && ' +
                budget_command('settle'))
    name = flat(ask)[:30] or '這封信'
    work.mkdir(parents=True, exist_ok=True)
    write_text(work / 'how.md', (f'# 卡住的回信：「{name}」\n\n第 {step} 回合的 call {cid}；{reserve}。\n' +
                                 how).rstrip() + '\n')
    again = ('現在用的是假 AI，不花錢。' if is_fake(cfg) else
             '現在用的是真 AI：如果上次 AI 其實已經回了，可能會多付一次錢。')
    title = f'「{name}」問 AI 時被打斷，先停下'
    body = (f'這封信「{name}」辦到一半，問 AI 時被打斷（例如程式被關掉），等了{minutes(waited)}還是不知道 AI 回了沒有，'
            '所以先停下這封，後面的信照常辦。系統不會自己重問。\n'
            '怎麼辦：\n① 什麼都不做：這封就停在這裡，不影響別的信。\n'
            '② 再寄一次這封信：會從頭重新問 AI。' + again + '\n\n'
            '細節見 `modules/up/ADVANCED.md` 的〈卡住的回信〉。\n')
    return title, body, f'卡住：「{name}」問 AI 時被打斷', '什麼都不做，或再寄一次這封信（細節看回信）'
def once(node, rnd):
    work = node / 'brain'
    work.mkdir(exist_ok=True)
    personal = [l for l in json.loads(mail(node, 'read', node.name, '--json')) if l.get('type') == 'mail']
    pending = read_json(str(work / 'pending.json'))
    if pending:
        finish(node, pending, personal)
        if pending['status'] != 'DONE':
            print(f'回合 {rnd}：' + trouble(pending['line'], pending.get('fix') or pending['body'].split('怎麼辦：')[-1]), flush=True)
        elif pending.get('usage_pending'):
            print(f'回合 {rnd}：已回信（AI 用量還沒對清，之後自己會對）', flush=True)
        return
    requests = []
    for letter in personal:
        if letter['status'] == 'REQUEST':
            requests.append(letter)
        else:
            mail(node, 'done', node.name, letter['id'])
    task = task_of(node)
    if not task or not any(l['id'] == task['id'] for l in requests):
        if task or not requests:
            drop_task(node, None)
        else:
            open_line(node, None)
        # 沒有進行中的任務（或信已被別人辦掉）：清掉殘留的 open 行與暫存
        task = None
    if not requests: return
    letter = next(l for l in requests if l['id'] == task['id']) if task else min(requests, key=fifo)
    ident, status, fix = letter['id'], 'DONE', ''
    usage_pending = False
    try:
        try:
            cfg = json.loads((node / '.aos/up.json').read_text()) if (node / '.aos/up.json').exists() else {}
            if not isinstance(cfg, dict):
                raise ValueError()
        except Exception:
            raise Trouble('設定檔 .aos/up.json 壞了', '刪掉它再跑 aos7-up <node>') from None
        cid = call_id(ident, task['step'] if task else 1)
        text = ask_ai(node, letter, cid, cfg)
        usage_pending = getattr(text, 'usage_pending', False)
        kind = kind_of(text)
        if kind == '要檔案：':
            text, kind = memory.want_step(memory.want_of(text)), '繼續：'
        if kind == '繼續：':
            note, stuck = step_on(node, letter, text, cfg)
            if note:
                print(f'回合 {rnd}：' + note, flush=True)
                return
            status, title, line = 'NEEDS-USER', stuck, '要你決定：' + stuck
            reply, fix = '原因：' + stuck + '\n怎麼辦：回信補資料或說下一步，再寄一次', '回信補資料或說下一步，再寄一次'
        elif kind == '要你決定：':
            reply, title, line = parse(text.replace('要你決定：', '回信：', 1), ident)
            status, fix = 'NEEDS-USER', '照回信補資料或決定，再寄一次'
        else:
            reply, title, line = parse(text, ident)
    except Later as e:
        path = work / 'unsure.json'
        if not e.unsure:
            path.unlink(missing_ok=True)
            print(f'回合 {rnd}：AI 回了、帳還沒對上，下回合再看同一筆', flush=True)
            return
        unsure = read_json(str(path), {}) or {}
        if unsure.get('call') != cid:
            unsure = dict(call=cid, id=ident, since=time.time())
            write_json(str(path), unsure)
        waited, limit = time.time() - unsure['since'], ai_deadline(cfg)
        if waited < limit:
            print(f'回合 {rnd}：AI 還沒確定回沒回（已等 {waited:.0f} 秒，滿 {limit:g} 秒就回信說卡住），下回合再看同一筆', flush=True)
            return
        status = 'BLOCKED'
        title, reply, line, fix = stuck_reply(node, cid, task['step'] if task else 1, waited, cfg, letter['title'])
    except Exception as e:
        status = 'BLOCKED'
        title, fix = (e.why, e.fix) if isinstance(e, Trouble) else ('讀寫沒完成', CHECK_FIX)
        reply, line = '原因：' + title + '\n怎麼辦：' + fix, '卡住：' + title
    pending = dict(id=ident, ask=letter['title'], status=status, title=title, body=reply, line=line, state_count=state_count(node, line), usage_pending=usage_pending, fix=fix)
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
