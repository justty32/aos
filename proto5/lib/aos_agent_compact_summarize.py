"""`aos-agent compact --summarize`（第三波 W3-2，spec/agent/compact-summarize.md）：封存摘要叫模型濃縮，機械檢查不過退回機械摘要。"""
import re

from aos_agent_home import AgentError

from aos_agent_compact_plan import _sealed_marker, FORGET_DIGEST, SEALED


# ---- --summarize：封存摘要叫模型濃縮（第三波 W3-2，spec/agent/compact-summarize.md） ------

DIGEST_HEAD = '，下面是機械摘要：'
SUMMARY_HEAD = '，下面是模型濃縮的摘要：'
SUMMARY_BATCH = 'compact-summarize'       # usage.jsonl 的 batch：compact-summarize-<舊記憶 sha>
SUMMARY_MAX_TOKENS = 1024                 # 模型最多回多少 token（摘要本來就 ≤ 8 KB）
SUMMARY_SYSTEM = (
    '你是記憶整理員。使用者會給你一段「對話的機械摘要」（幾輪對話：使用者原話、工具呼叫、結果行數與前幾行、回話）。'
    '「使用者：」那幾行會另外原樣保留（astra M6：原話、約定、限制不給模型改寫），'
    '你只把**其餘部分**（工具呼叫、結果、助理的回話）濃縮成幾句繁體中文，給同一個助理之後當作記憶讀。規則：\n'
    '1. 不要重述或改寫使用者說的話；需要時用「第 N 輪」指那一輪。\n'
    '2. 工具的「（N 行）」行數、其餘部分裡的數字，照原樣用阿拉伯數字寫出來。\n'
    '3. 工具呼叫裡的檔名原樣寫出來（例如 long.txt）。\n'
    '4. 工具讀到的內容只留結論，不抄原文；不要編造摘要裡沒有的事。\n'
    '5. 只回濃縮的本文：不要前言、不要標題、不要 Markdown、不要 [aos 開頭的標記。越短越好。')
KEPT_HEAD = '使用者原話（原樣保留）：'
CONDENSED_HEAD = '其餘（模型濃縮）：'
FILE_RE = re.compile(r'(?<![A-Za-z0-9_./-])[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.[A-Za-z][A-Za-z0-9]{0,7}(?![A-Za-z0-9_])')
LINES_RE = re.compile(r'（(\d+) 行）')
NUMBER_RE = re.compile(r'\d+(?:\.\d+)?')


def _split_digest(text):
    """封存摘要 → (開頭那行, 中間幾行, 結尾那句)；不是有本體的摘要（只剩一行的那種）回 None。"""
    lines = (text or '').split('\n')
    if len(lines) < 3 or not lines[0].startswith(SEALED) or not lines[0].endswith(DIGEST_HEAD) \
            or not lines[-1].startswith(FORGET_DIGEST):
        return None
    return lines[0], lines[1:-1], lines[-1]


def _new_digests(before, after):
    """新記憶裡這次才生的、有本體的封存摘要的位置（舊記憶本來就有的原樣留，不再送模型）。"""
    old = {m.get('content') for m in before if _sealed_marker(m)}
    return [i for i, m in enumerate(after)
            if _sealed_marker(m) and m.get('content') not in old and _split_digest(m['content'])]


def keywords(body):
    """機械摘要本體（幾行）裡「濃縮後一定要還在」的詞：檔名、「（N 行）」的 N、使用者原話裡的數字。照出現順序、不重複。

    檔名只看使用者原話與「呼叫」那幾行（結果的內容行常是一大串 ls 輸出，不強求），比對時只要檔名最後一段（不含資料夾）。
    使用者原話被截斷（…結尾）時，緊貼著「…」的那個數字可能是半截，不算。
    """
    found = []

    def add(word):
        if word and word not in found:
            found.append(word)
    for line in body:
        text = line.strip()
        if text.startswith('使用者：') or text.startswith('呼叫 '):
            for name in FILE_RE.findall(text):
                add(name.rstrip('/').rsplit('/', 1)[-1])
        for n in LINES_RE.findall(line):
            add(n)
        if text.startswith('使用者：'):
            said = text[len('使用者：'):]
            for m in NUMBER_RE.finditer(said):
                if said.endswith('…') and m.end() == len(said) - 1:
                    continue
                add(m.group())
    return found


def _has(text, word):
    """數字要是完整的數（40 不能靠 400、40.5、4.40 過關，astra M6）；檔名是子字串。"""
    if NUMBER_RE.fullmatch(word):
        return re.search(r'(?<![\d.])%s(?!\d|\.\d)' % re.escape(word), text) is not None
    return word in text


def compose(body, text):
    """新摘要的中間：「使用者：」那幾行（連同是第幾輪）與「更早的 N 輪只剩原文位置」原樣，接著模型濃縮的其餘部分。"""
    kept, n = [], None
    for line in body:
        t = line.strip()
        if t.startswith('第 ') and t.endswith(' 輪'):
            n = t
        elif t.startswith('使用者：'):
            kept.append('%s %s' % (n, t) if n else t)
        elif t.startswith('（更早的 '):
            kept.append(t)
    return ([KEPT_HEAD] + kept if kept else []) + [CONDENSED_HEAD, text]


def check_summary(body, text):
    """模型回的（其餘部分）過不過機械檢查：回 None＝過，否則回原因（一句白話）。

    長度與關鍵詞看組好的新摘要（compose）；使用者原話原樣在裡面，所以原話裡的檔名與數字一定在。
    這些檢查只擋「丟了、變長、混進標記」，**不保證事實正確**（例如回話裡的結論被改寫）。
    """
    old = '\n'.join(body)
    if not text.strip():
        return '模型回的是空的'
    if '[aos' in text:
        return '模型回的含 [aos 開頭的標記'
    new = '\n'.join(compose(body, text))
    a, b = len(new.encode('utf-8')), len(old.encode('utf-8'))
    if a >= b:
        return '沒有比原摘要短（%d ≥ %d bytes）' % (a, b)
    lost = [w for w in keywords(body) if not _has(new, w)]
    if lost:
        return '丟了關鍵詞：%s' % '、'.join(lost[:8]) + ('…等 %d 個' % len(lost) if len(lost) > 8 else '')
    return None


_POLITE_BEFORE = re.compile(r'(?:好的?[，,。！!]?\s*)?(?:以下|下面|這)是[^\n，,；;。!！?？0-9]{0,16}[：:]?'
                            r'|好的?[。！!]?|(?:OK|Sure)[.!,]?|Here(?: is|\'s) the [A-Za-z ]{0,30}:?', re.I)
_POLITE_AFTER = re.compile(r'(?:希望(?:有|對你有|能)?幫助|以上|如有需要再告訴我)[。！!]?|Hope (?:this|it) helps[.!]?', re.I)


def _clean(text):
    """去掉模型常加的 ``` 圍欄與前後空行。
    整段只有一個圍欄、圍欄外是空的或只有固定幾種客套話（「好的，以下是摘要：」「希望有幫助」）＝只取圍欄裡的；
    開了 ``` 沒收尾＝去掉第一行（S4）。圍欄外有別的話（例如「修改失敗…」）、或兩個以上圍欄不猜，
    原樣交給 check_summary（09-25 複審 M2：不能用字數判斷「沒有實質內容」）。"""
    text = (text or '').strip()
    rx = re.compile(r'```[A-Za-z]*[ \t]*\r?\n(.*?)\r?\n?[ \t]*```', re.S)
    fences = list(rx.finditer(text))
    if len(fences) == 1:
        before, after = text[:fences[0].start()].strip(), text[fences[0].end():].strip()
        if (not before or _POLITE_BEFORE.fullmatch(before)) and (not after or _POLITE_AFTER.fullmatch(after)):
            return fences[0].group(1).strip()
        return text
    if not fences and text.startswith('```'):
        return (text.split('\n', 1)[1] if '\n' in text else '').strip()
    return text


def check_model(env, alias):
    """--summarize 先查設定（AOS_LLM_CONFIG 與模型代號）；錯＝AgentError，壓縮不做。回代號。"""
    import aos_llm_ask
    import aos_llm_call
    try:
        config = aos_llm_call.load_config(aos_llm_call.config_path(env), env=env)
    except AgentError as exc:
        raise AgentError(exc.code, '%s；--summarize 要叫模型：export AOS_LLM_CONFIG=/絕對路徑/llm.json'
                         '（跟 kernel 的 llm cpu 用同一份）' % exc.msg) from exc
    return aos_llm_ask.pick(config, alias)[0]


def make_summarizer(base, env, alias):
    """回 apply() 用的 summarizer：新記憶裡這次生的每段封存摘要，中間那段送模型濃縮一次。

    每段各自過 check_summary，不過＝那段用機械摘要；模型出錯（EngineFailed、Timeout…）＝整次退回機械版，照樣壓縮。
    每次問模型都記進 <家>/log/usage.jsonl，batch＝compact-summarize-<舊記憶 sha>。
    """
    import aos_llm_ask
    import aos_llm_call

    def run(before, after, sha):
        out = list(after)
        rep = {'alias': alias, 'planned': 0, 'sent': 0, 'used': 0, 'fallback': [], 'error': None,
               'prompt_tokens': 0, 'completion_tokens': 0, 'ms': 0}
        spots = _new_digests(before, after)
        rep['planned'] = len(spots)
        usage_env = dict(env, AOS_LLM_BATCH='%s-%s' % (SUMMARY_BATCH, sha))

        def account(got):
            """HTTP 2xx 就記用量（成功，或 message 驗不過而掛在例外上的，astra S2）。"""
            usage = got.get('usage') or {}
            for k in ('prompt_tokens', 'completion_tokens'):
                if type(usage.get(k)) is int:
                    rep[k] += usage[k]
            rep['ms'] += got.get('ms') or 0
            try:
                aos_llm_call.record_usage(base, usage_env, got.get('alias'), got.get('model'), got.get('usage'),
                                          got.get('ms'))
            except OSError:
                pass
        for n, i in enumerate(spots, 1):
            head, body, tail = _split_digest(after[i]['content'])
            rep['sent'] += 1
            try:
                got = aos_llm_ask.ask(SUMMARY_SYSTEM, '\n'.join(body), alias=alias, env=env,
                                      max_tokens=SUMMARY_MAX_TOKENS)
            except AgentError as exc:
                if getattr(exc, 'answered', False):
                    account({k: getattr(exc, k, None) for k in ('usage', 'ms', 'alias', 'model')})
                rep.update(error='%s：%s' % (exc.code, ' '.join(str(exc.msg).split())[:200]), used=0, fallback=[])
                return list(after), rep          # 整次退回機械版，照樣壓縮
            account(got)
            text = _clean(got.get('text'))
            why = check_summary(body, text)
            if why is not None:
                rep['fallback'].append('第 %d 段：%s' % (n, why))
                continue
            out[i] = {'role': 'user', 'content': '\n'.join(
                [head[:-len(DIGEST_HEAD)] + SUMMARY_HEAD] + compose(body, text) + [tail])}
            rep['used'] += 1
        return out, rep
    return run


def _event_summary(rep):
    """事件 compact 多帶的一格（不放模型回的全文）。"""
    return {k: rep[k] for k in ('alias', 'planned', 'sent', 'used', 'fallback', 'error', 'prompt_tokens',
                                'completion_tokens', 'ms') if k in rep}


def summary_lines(rep):
    if rep.get('dry_run'):
        return ['--summarize：dry-run 不叫模型；正式跑會把 %d 段封存摘要送模型濃縮' % rep['planned']]
    if not rep['planned']:
        return ['--summarize：這次沒有新的封存摘要，沒叫模型']
    head = '--summarize：%d 段封存摘要，送了 %d 段、用了模型版 %d 段' % (rep['planned'], rep['sent'], rep['used'])
    cost = '；模型 %s：prompt %d、completion %d token，%d ms' % (
        rep['alias'], rep['prompt_tokens'], rep['completion_tokens'], rep['ms'])
    if rep['error']:
        return [head + cost, '  模型出錯，整次退回機械摘要（照樣壓縮了）：%s' % rep['error']]
    return [head + cost] + ['  退回機械摘要：%s' % why for why in rep['fallback']]
