"""LLM 候選來源：鎖外組提示、經 llmcall 交付原文，再走既有 author 驗證。"""
import json
import os
import re
import subprocess
import tempfile

from aos7_author import (Node, PACKS, Refuse, Unknown, canon, check_rid,
                         load_toolcards, propose, result, sha256)

LLMCALL_BIN = os.path.join(PACKS, 'llmcall', 'bin', 'aos7-llmcall')
SYSTEM = ('你是 aos 的工作流作者。只輸出一個 JSON 物件，不加說明、不加 Markdown 圍欄。'
          '只能組合工具卡上的工具；不宣告 finite、idempotent、argv 或其他執行屬性。'
          # sol 經 LiteLLM 會先講開場白；這句重放 4/4 有效（notes/play/2026-10-09-real-ai/litellm-truncation.md）
          '你沒有任何工具、不能看檔或跑指令，所需資料都在使用者訊息裡。不要說明計畫、不要開場白，第一個字元就是 {。')
RULES = '''候選恰含 v、mode、intent、start、steps、ends；v=1，只收 keep，最多 16 步、64 KiB。
每步恰含 id、tool、args、ok、fail；id 唯一，start 與跳轉目標必須存在，所有步可達、跳轉不可成環。
args 必須符合工具卡：不得缺少或多餘參數，型別必須相符，有 value 的值完全相等。
${job}/<輸入檔名> 是需求輸入；輸入只在 ${job}/ 下，不讀 node 原檔。
${out}/… 是本版寫入或讀取產物；${request} 是本步 request；${req:<步id>} 取前一步成功採用的 request。
role=req 的引用在每條可達路徑上都必須已成功，且引用步的工具必須符合卡的 tool。
寫入及同目錄 <dst>.tmp 都只能在 ${out}/ 下；禁止絕對路徑、..、空段、NUL、其他展開及 symlink 逃逸。
只能用需求 tools 白名單。finite、idempotent、expect、argv、run 等執行屬性由卡決定，不可在候選宣告。
輸出嚴格 UTF-8 JSON，不得重複鍵、NaN 或 Infinity；不會自動修復 JSON。'''
SCHEMA = {'v': 1, 'mode': 'keep', 'intent': 'str', 'start': '步id',
          'steps': [{'id': '步id', 'tool': '工具名', 'args': {'參數': '值'},
                     'ok': '步id或end名', 'fail': '步id或end名'}],
          'ends': {'end名': 'ok|failed'}}
# --llm 不給模型＝先便宜後升級：被拒才換下一級（實測見 notes/play/2026-10-09-real-ai/ef3.md）
AUTO = '\0auto'      # --llm 沒給值（命令列給不出 NUL，不會撞到真模型名）
LADDER = ('chatgpt-gpt-6-luna-nothink', 'chatgpt-gpt-6-sol-high', 'chatgpt-gpt-6-astra-high')


def rung_call(call, i):
    if call is None or i == 0:
        return call
    suffix = '-r%d' % i
    return call + suffix if len(call + suffix) <= 64 else '%s-%s%s' % (call[:50], sha256(call.encode())[:8], suffix)


def climb(attempt, rejected):
    """attempt(model, i) 回 propose 結果；rejected(r)＝模型答了、候選確實被拒，才升級，其餘立刻停。"""
    rounds = []
    for i, model in enumerate(LADDER):
        r = attempt(model, i)
        info = r.get('llm') or {}
        rounds.append(dict(model=model, call_id=info.get('call_id'), why=r.get('why'), usage=info.get('usage')))
        if r.get('why') != 'invalid' or info.get('outcome') != 'answered' or not rejected(r):
            break
    return dict(r, rounds=rounds)


def prompt_request(node, rid, model):
    """只讀已登記需求與白名單卡；同內容同模型回同 bytes。"""
    check_rid(rid)
    req, _ = node.request(rid)
    cards = load_toolcards()['tools']
    selected = {tid: {key: cards[tid][key] for key in ('argv', 'params', 'artifacts')}
                for tid in sorted(req['tools'])}
    user = canon({'request': req, 'toolcards': selected, 'candidate_schema': SCHEMA,
                  'rules': RULES}).decode('utf-8')
    return canon({'litellm': {'model': model, 'messages': [
        {'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}})


def propose_llm(node, rid, *, model, call=None, **kw):
    if model != AUTO:
        return propose_one(node, rid, model=model, call=call, **kw)
    return climb(lambda m, i: propose_one(node, rid, model=m, call=rung_call(call, i), **kw),
                 lambda r: bool(r.get('_rejected')))


def propose_one(node, rid, *, model, budget, call=None, reserve=1000000,
                deadline=None, patience=5, llmcall_bin=LLMCALL_BIN, env=None,
                prompt_out=None, auto=False):
    nd = node if isinstance(node, Node) else Node(node)
    llm = dict(model=model, call_id=call, exit=None, outcome=None, usage=None,
               used=None, billing=None, reserve=reserve, receipt_path=None)
    try:
        raw = prompt_request(nd, rid, model)
        call_id = call or '%s-%s' % (('%s-%s' % (rid, re.sub('[^A-Za-z0-9_-]', '', model)))[:55], sha256(raw)[:8])
        llm['call_id'] = call_id
        if prompt_out is not None:
            path = os.path.join(nd.node, os.fspath(prompt_out))
            with open(path, 'wb') as stream:
                stream.write(raw)
            return result(True, rid=rid, prompt_out=os.path.abspath(path), llm=llm)
        with tempfile.TemporaryDirectory(prefix='aos7-author-llm-') as tmp:
            request_path = os.path.join(tmp, 'request.json')
            with open(request_path, 'wb') as stream:
                stream.write(raw)
            args = ['python3', os.fspath(llmcall_bin), 'call', os.fspath(budget),
                    '--holder', 'author', '--call', call_id, '--logical', 'author/' + rid,
                    '--request', request_path, '--reserve', str(reserve), '--patience', str(patience)]
            if deadline is not None:
                args += ['--deadline', str(deadline)]
            proc = subprocess.run(args, cwd=nd.node, env=env, capture_output=True, text=True, encoding='utf-8')
            llm['exit'] = proc.returncode
            try:
                receipt = json.loads(proc.stdout.strip().splitlines()[-1])
                if not isinstance(receipt, dict):
                    receipt = {}
            except (ValueError, IndexError):
                receipt = {}
            for key in ('outcome', 'usage', 'used', 'billing'):
                llm[key] = receipt.get(key)
            # llmcall 的證據屬 budget 所在 node，而非 author 的 cwd。
            bd = os.path.realpath(os.path.join(nd.node, os.fspath(budget)))
            path = os.path.join(os.path.dirname(os.path.dirname(bd)), 'llmcall', os.path.basename(bd), call_id, 'receipt.json')
            if os.path.isfile(path):
                llm['receipt_path'] = path
            if proc.returncode not in (0, 4) or receipt.get('outcome') != 'answered' \
                    or not isinstance(receipt.get('text'), str):
                return result(False, 'unknown' if proc.returncode == 3 else 'invalid', rid=rid, llm=llm)
            candidate_path = os.path.join(tmp, 'candidate.json')
            with open(candidate_path, 'wb') as stream:
                stream.write(receipt['text'].encode('utf-8'))
            return dict(propose(nd, rid, candidate_path=candidate_path, auto=auto), llm=llm)
    except Refuse as exc:
        return result(False, exc.why, rid=rid, error=exc.msg, llm=llm)
    except (ValueError, KeyError, UnicodeError) as exc:
        return result(False, 'invalid', rid=rid, error=str(exc), llm=llm)
    except (Unknown, OSError) as exc:
        return result(False, 'unknown', rid=rid, error=str(exc), llm=llm)
