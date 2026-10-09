"""aos 學徒、llmcall 審查與踩坑學習；三關一律交給子程序。"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from argparse import Namespace
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
TOP = HERE.parents[1]
sys.path.insert(0, str(HERE / 'checkers'))
from aos_three_gates import REVIEW_CRITERIA, request, brief, strict
from aos7_author_llm import APPRENTICE_LADDER, AUTO, LADDER, climb, rung_call  # noqa: E402

LLMCALL = HERE.parent / 'llmcall/bin/aos7-llmcall'
# sol 經 LiteLLM 會先講開場白；這句重放 4/4 有效（notes/play/2026-10-09-real-ai/litellm-truncation.md）
NO_TOOLS = '你沒有任何工具、不能看檔或跑指令，所需資料都在使用者訊息裡。不要說明計畫、不要開場白，第一個字元就是 {}。'
SYSTEM = '你是 aos 的學徒工程師，只輸出一個 JSON 物件，不加說明、不加 Markdown 圍欄。' + NO_TOOLS.format('{')
RULES = '''files 的鍵都在 toolcard.root 下，只新增一個原型尚不存在的 root，不修改既有檔案；必有 toolcard.required 的所有檔。
入口 ≤12 行、會被設成可執行，使用 #!/usr/bin/env python3。測試只收 <root>/tests/test_*.py，檔名不得與原型裡既有測試檔撞名，建議 test_<name>_*.py。
每檔 ≤8192 bytes、全份候選 JSON ≤65536 bytes、檔數 ≤ min(工具卡 limits.max_files, 需求 scope.max_files)。
README 必要章節要在行首（可加「- 」）且不在程式碼圍欄裡；README 相對連結不能壞（wf-lint）。
row 單行、以卡的 row.prefix 開頭、以 | 結尾，其中相對連結相對索引檔 row.file 所在資料夾。
第二關在 bwrap 沙箱：只有標準庫、斷網、HOME 是空的 /tmp/home、只有暫存樹可寫；python3 tests/run_all.py <root>/tests 在原型根（proto7-2）cwd 跑，每個測試資料夾以自己為 top_level_dir discover，至少要真的跑 1 項測試。
之後需求指定的獨立答案檢查器以 python3 check_answer.py <原型根> <fixture> 跑你的入口，輸出格式要完全照需求 work／accept。
第三關 rules 掃所有非 .md／.json 檔（含無副檔名入口），不得出現 shell=True、os.system(、import/from socket/urllib/http/requests、eval(／exec(；有指定模型時，接著另一個模型審查全部檔案。'''


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prompt(model, system, user):
    return canon({'litellm': {'model': model, 'messages': [
        {'role': 'system', 'content': system}, {'role': 'user', 'content': canon(user).decode('utf-8')}]}})


def prompt_request(req_path, model, context=(), gotchas=None, previous=None, feedback=None):
    req, card = request(Path(req_path))
    card = {k: card[k] for k in ('root', 'required', 'entry', 'entry_max_lines', 'tests',
                               'row', 'readme_must', 'limits', 'review_rules')}
    for key in ('root', 'entry'):
        card[key] = card[key].format(name=req['name'])
    card['row'] = dict(card['row'], prefix=card['row']['prefix'].format(name=req['name']))
    contents = {}
    for filename in context or ():
        path = Path(filename).resolve()
        key = path.relative_to(TOP).as_posix() if path.is_relative_to(TOP) else path.name
        contents[key] = path.read_text(encoding='utf-8')
    user = dict(brief=brief(req), toolcard=card, candidate_schema={
        'v': 1, 'rid': req['rid'], 'kind': req['kind'], 'name': req['name'],
        'files': {card['root'] + '/相對路徑': '檔案全文'}, 'row': '索引檔要新增的一列',
        'report': '# REPORT …（末尾必有「以後交接書該點名的工具」一節）'}, rules=RULES, context=contents)
    if gotchas:
        user['gotchas'] = Path(gotchas).read_text(encoding='utf-8')
    if previous and feedback:
        user['previous_candidate'] = Path(previous).read_text(encoding='utf-8')
        check = feedback if isinstance(feedback, dict) else strict(Path(feedback).read_bytes())
        if not isinstance(check, dict):
            raise ValueError('feedback 必須是檢查 JSON 物件')
        check = check.get('check', check)
        if not isinstance(check, dict):
            raise ValueError('feedback.check 必須是物件')
        user['feedback'] = {k: check.get(k) for k in ('failed_gate', 'gates')}
        user['rules'] += '\n上一份沒過，照 feedback 修正後交出完整的新候選。'
    return prompt(model, SYSTEM, user)


def call_info(model, rid, raw, call_id=None, prefix='', reserve=1000000):
    call_id = call_id or ('%s%s-%s' % (prefix, rid, re.sub('[^A-Za-z0-9_-]', '', model)))[:55] + '-' + sha(raw)[:8]
    return dict(model=model, call_id=call_id, exit=None, outcome=None, usage=None,
                used=None, billing=None, reserve=reserve, receipt_path=None)


def llmcall(node, budget, call_id, logical, raw, reserve, deadline, patience, env, model):
    info = call_info(model, '', raw, call_id, reserve=reserve)
    with tempfile.TemporaryDirectory(prefix='aos7-author-aos-') as tmp:
        path = Path(tmp) / 'request.json'
        path.write_bytes(raw)
        args = ['python3', str(LLMCALL), 'call', str(budget), '--holder', 'author',
                '--call', call_id, '--logical', logical, '--request', str(path),
                '--reserve', str(reserve), '--patience', str(patience)]
        if deadline is not None:
            args += ['--deadline', str(deadline)]
        proc = subprocess.run(args, cwd=node, env=env, capture_output=True, text=True, encoding='utf-8')
    info['exit'] = proc.returncode
    try:
        receipt = json.loads(proc.stdout.strip().splitlines()[-1])
        if not isinstance(receipt, dict):
            receipt = {}
    except (ValueError, IndexError):
        receipt = {}
    for key in ('outcome', 'usage', 'used', 'billing'):
        info[key] = receipt.get(key)
    bd = Path(node, budget).resolve()
    path = bd.parent.parent / 'llmcall' / bd.name / call_id / 'receipt.json'
    if path.is_file():
        info['receipt_path'] = str(path)
    return receipt, info


def delivery(a, req, model, raw, prefix='', explicit=True):
    info = call_info(model, req['rid'], raw, a.call if explicit else None, prefix, a.reserve)
    receipt, info = llmcall(Path.cwd(), a.budget, info['call_id'], ({'rv-': 'author-review/', 'ln-': 'author-learn/'}.get(prefix, 'author/')) + req['rid'], raw,
                            a.reserve, a.deadline, a.patience, None, model)
    why = None
    if info['exit'] not in (0, 4) or receipt.get('outcome') != 'answered' or not isinstance(receipt.get('text'), str):
        why = 'unknown' if info['exit'] == 3 else 'invalid'
    return receipt.get('text'), info, why


def gates(a, cmd, candidate, reviewer):
    args = ['python3', str(HERE / 'checkers/aos_three_gates.py'), cmd, a.arg,
            str(candidate), '--reviewer', reviewer]
    if a.no_scope:
        args += ['--no-scope']
    for key in ('repo', 'ref'):
        if getattr(a, key):
            args += ['--' + key, getattr(a, key)]
    proc = subprocess.run(args, capture_output=True, timeout=950)
    try:
        if len(proc.stdout.strip().splitlines()) != 1:
            raise ValueError('檢查器 stdout 必須單行')
        out = strict(proc.stdout)
        if not isinstance(out, dict):
            raise ValueError('檢查器輸出不是物件')
    except (ValueError, UnicodeError):
        return {'ok': False, 'unknown': '檢查器 stdout 不是單行 JSON'}, 'unknown'
    why = {0: None, 1: ('conflict' if out.get('branch') and out.get('failed_gate') is None else 'invalid'),
           2: 'invalid', 3: 'unknown'}.get(proc.returncode, 'unknown')
    if proc.returncode == 1 and why == 'invalid':
        out['_rejected'] = True      # 某關沒過＝被拒（退 1）；why 照舊 invalid，main 印 JSON 前拿掉
    message = proc.stderr.decode('utf-8', 'replace').strip()
    if message and 'error' not in out:
        out['error'] = message.removeprefix('aos7-gates: ')
    return out, why


def history_summary(path):
    doc = strict(Path(path).read_bytes())
    if not isinstance(doc, dict):
        raise ValueError('history 必須是 JSON 物件')
    check = doc.get('check') or doc
    if not isinstance(check, dict) or not isinstance(check.get('gates', {}), dict) or any(not isinstance(g, dict) for g in check.get('gates', {}).values()):
        raise ValueError('history.check／gates 格式不合')
    return {'failed_gate': check.get('failed_gate'), 'issues': check.get('issues', []),
            'gates': {n: {'issues': g.get('issues', [])} for n, g in check.get('gates', {}).items()}}


def learn(a, req, out):
    into = Path(a.into).resolve()
    if not into.is_file():
        return dict(out, why='invalid', error='--into 必須是既有檔案')
    original = into.read_bytes()
    existing = original.decode('utf-8')
    raw = prompt(a.llm, '你是 aos 的學徒工程師，只回踩坑條目，不加說明或 Markdown 圍欄。' + NO_TOOLS.format('-'), {
        'brief': brief(req), 'history': [history_summary(p) for p in a.history], 'existing': existing,
        'rules': '只回 1～8 行，每行以 - 開頭並在 - 後加空格，每行 ≤200 字，寫「下次寫 aos 工具／模組前要先知道的事」，不重複既有條目。'})
    text, info, why = delivery(a, req, a.llm, raw, 'ln-')
    out.update(into=str(into), added=[], llm=info)
    if why:
        return dict(out, why=why, _rejected=why == 'invalid')
    lines = text.splitlines()
    if not 1 <= len(lines) <= 8 or any(not x.startswith('- ') or not x[2:].strip() or len(x) > 200 for x in lines) or len(set(lines)) != len(lines):
        return dict(out, why='invalid', error='踩坑條目格式不合或重複', _rejected=True)
    try:
        fd = os.open(into, os.O_RDWR | os.O_APPEND)
    except FileNotFoundError:
        return dict(out, why='invalid', error='--into 必須是既有檔案')
    with os.fdopen(fd, 'r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            current = into.stat()
        except FileNotFoundError:
            return dict(out, why='invalid', error='--into 必須是既有檔案')
        opened = os.fstat(stream.fileno())
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            return dict(out, why='invalid', error='--into 在等待鎖時被替換')
        # 不使用等待模型之前的內容驗重；鎖住後重讀最新版本。
        latest = stream.read().decode('utf-8')
        if any(x in latest.splitlines() for x in lines):
            return dict(out, why='invalid', error='踩坑條目重複', _rejected=True)
        stream.write(('\n## %s（%s）\n' % (req['rid'], a.llm) + '\n'.join(lines) + '\n').encode('utf-8'))
    return dict(out, ok=True, why=None, added=lines)


def close_aos(a, req, out):
    from aos7_author import Node, Unknown, fact, N, OK, write_json
    nd = Node()
    try:
        with nd.lock():
            path = nd.path(req['rid'], 'receipt.json')
            st, doc = fact(path)
            rsha = sha(Path(a.arg).read_bytes())
            if fact(nd.path(req['rid'], 'request.json'))[0] != N:
                return dict(out, close_skipped='同 rid 已有 CSV 需求帳，不寫結案標記')
            if st not in (N, OK):
                raise Unknown('結案標記讀不到：%s' % doc)
            if st != N:
                valid = (st == OK and isinstance(doc, dict) and doc.get('v') == 1
                         and doc.get('rid') == req['rid'] and doc.get('request_sha') == rsha
                         and doc.get('closed') is True and doc.get('kind') == req['kind']
                         and isinstance(doc.get('closed_at'), str) and isinstance(doc.get('versions'), dict)
                         and all(isinstance(v, dict) and set(v) == {'job', 'branch', 'commit'} for v in doc['versions'].values()))
                if not valid:
                    return dict(out, close_skipped='既有 receipt 不是此需求的 aos 結案標記，保留原樣')
            else:
                doc = dict(v=1, rid=req['rid'], request_sha=rsha, closed=True, kind=req['kind'],
                           closed_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), versions={})
            doc['versions'][out['candidate_sha']] = {k: out[k] for k in ('job', 'branch', 'commit')}
            write_json(path, doc)
        return out
    except (Unknown, OSError) as exc:
        return dict(out, ok=False, why='unknown', error='分支 %s 已建（%s），結案標記未完成：%s' % (out['branch'], out['commit'], exc))


def main_aos(a):
    out = dict(ok=False, why=None, llm=None, review=None)
    try:
        try:
            req, _ = request(Path(a.arg))
        except OSError as exc:
            return dict(out, why='invalid', error=str(exc))
        out.update(rid=req['rid'], kind=req['kind'], name=req['name'])
        if a.llm == AUTO and a.cmd == 'learn':
            a.llm = LADDER[0]
        if a.cmd == 'learn':
            return learn(a, req, dict(ok=False, why=None, rid=req['rid'],
                                      into=str(Path(a.into).resolve()), added=[], llm=None))
        if a.cmd == 'publish':
            if a.repo and (a.reviewer or 'rules').startswith('file:'):
                check, why = gates(a, 'check', a.candidate, 'rules')
                if why is not None or not check.get('ok'):
                    return {**out, **check, 'why': why or 'invalid'}
            check, why = gates(a, 'publish', a.candidate, a.reviewer or 'rules')
            out = {**out, **check, 'why': why}
            if out.get('ok') and why is None:
                return close_aos(a, req, out)
            return out
        if a.llm != AUTO:
            return propose_one(a, req, out)
        prev = [a.previous, a.feedback]

        def attempt(model, i):
            # 升級時把上一級的候選與檢查結果當重問交下一級；各級候選分檔，例外只結束這一級
            out_i = None if not a.out or i == 0 else '%s-r%d%s' % (os.path.splitext(a.out)[0], i, os.path.splitext(a.out)[1])
            b = Namespace(**dict(vars(a), llm=model, call=rung_call(a.call, i), out=out_i or a.out,
                                 previous=prev[0], feedback=prev[1]))
            mine = dict(out)
            try:
                r = propose_one(b, req, mine)
            except (ValueError, UnicodeError, KeyError, TypeError) as exc:
                return dict(mine, ok=False, why='invalid', error=str(exc))
            except (OSError, subprocess.TimeoutExpired) as exc:
                return dict(mine, ok=False, why='unknown', error=str(exc))
            if r.get('candidate_path') and isinstance(r.get('check'), dict):
                prev[:] = [r['candidate_path'], r['check']]
            return r
        # 只有三關（含審查）真的擋下（檢查器退 1）才升級；審查模型沒答成、檢查器參數錯（退 2）不算
        return climb(attempt, lambda r: isinstance(r.get('check'), dict) and bool(r['check'].get('_rejected')),
                     APPRENTICE_LADDER)
    except (ValueError, UnicodeError, KeyError, TypeError) as exc:
        return dict(out, ok=False, why='invalid', error=str(exc))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return dict(out, ok=False, why='unknown', error=str(exc))


def propose_one(a, req, out):
    candidate = Path(a.candidate).resolve() if a.candidate else None
    if a.llm:
        raw = prompt_request(a.arg, a.llm, a.context, a.gotchas, a.previous, a.feedback)
        info = call_info(a.llm, req['rid'], raw, a.call, reserve=a.reserve)
        out['llm'] = info
        if a.prompt_out:
            path = Path(a.prompt_out).resolve()
            path.write_bytes(raw)
            return dict(out, ok=True, prompt_out=str(path))
        text, info, why = delivery(a, req, a.llm, raw)
        out['llm'] = info
        if why:
            return dict(out, why=why, _rejected=why == 'invalid')
        candidate = Path(a.out).resolve() if a.out else Path.cwd() / 'author/aos' / req['rid'] / (info['call_id'] + '.json')
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(text.encode('utf-8'))
    try:
        data = candidate.read_bytes()
    except OSError as exc:
        return dict(out, why='invalid', error=str(exc))
    out.update(candidate_path=str(candidate), candidate_sha=sha(data), job=req['rid'] + '_' + sha(data)[:8])
    # 唯一暫存路徑避免來源或同 sha 快照被其他呼叫覆寫。
    with tempfile.NamedTemporaryFile(dir=candidate.parent, prefix=sha(data)[:8] + '-',
                                     suffix='.snapshot.json', delete=False) as stream:
        stream.write(data)
        snapshot = Path(stream.name)
    try:
        return propose_checks(a, req, out, candidate, snapshot, data)
    finally:
        snapshot.unlink()


def propose_checks(a, req, out, candidate, snapshot, data):
    check, why = gates(a, 'check', snapshot, 'rules')
    out.update(rules_check=check, check=check)
    if check.get('candidate_sha') != sha(data):
        return dict(out, ok=False, why='invalid', error='candidate_sha 與快照不符')
    if check.get('ok') and why is None:
        reviewer = a.reviewer or 'rules'
        if a.review_llm:
            raw = prompt(a.review_llm, '你是 aos 的審查人，只回一個 JSON 物件 {"verdict":"accept"|"reject","reasons":[字串…]}，不加圍欄。' + NO_TOOLS.format('{'), {
                'brief': brief(req), 'candidate': data.decode('utf-8'),
                'gates': {k: check['gates'][k] for k in ('1', '2')},
                'rules': '①② 已由檢查器在沙箱跑過；你只讀碼。審查所有檔案是否符合需求、工具卡與安全界線。' + REVIEW_CRITERIA})
            text, info, why = delivery(a, req, a.review_llm, raw, 'rv-', explicit=False)
            out['review'] = {'llm': info, 'path': None}
            if why:
                return dict(out, why=why, _rejected=why == 'invalid')
            path = candidate.parent / ('review-' + info['call_id'] + '.json')
            path.write_bytes(text.encode('utf-8'))
            out['review']['path'] = str(path)
            reviewer = 'file:' + str(path)
        if reviewer != 'rules':
            check, why = gates(a, 'check', snapshot, reviewer)
            out['check'] = check
    if any(result.get('candidate_sha') != sha(data) for result in (out['rules_check'], out['check'])):
        return dict(out, ok=False, why='invalid', error='candidate_sha 與快照不符')
    if check.get('error') and 'error' not in out:
        out['error'] = check['error']
    if a.llm and why == 'invalid':
        out['_rejected'] = True      # 模型交的候選連形狀都不對＝被拒（退 1），不是使用者給錯
    return dict(out, ok=bool(check.get('ok')) and why is None, why=why)
