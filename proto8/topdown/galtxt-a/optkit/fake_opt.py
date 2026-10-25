"""fake_opt - 優化模式的假腦劇本（round4-selfopt.md § 4；離線測試用，不是工具）。writer/brain.py 在 GALTXT_OPT=1 而且沒設 AOS_BRAIN_URL 時 import 這支、叫 step()。
照被優化的子樹（OPTKIT_SUBTREE）挑劇本，照固定順序一步叫一支工具，叫完交一段純文字報告：
  writer               opt_describe → opt_history → opt_extract（close，內建 12 行查表程式）→ opt_test → opt_note → 交稿
  …/voice              opt_describe → opt_read _entry → opt_edit _entry（口癖照 idx 輪替）→ opt_edit tool.json（加 idx）→ opt_test → opt_note → 交稿
  其他                 opt_describe → opt_note → 交稿
壞劇本（GALTXT_FAKE_OPT）：cheat＝叫工具改尺／寫測試／讀正解（工具層擋下），交稿前再用「程式」直接改拷貝裡的 data/dims.json（模擬跑起來的程式繞過工具；accept 要抓到）；
break＝把 voice/_entry 改成語法錯 → opt_test 紅 → 交稿（accept 要拒）。"""
import json, os, sys

sys.dont_write_bytecode = True

CLOSE_CODE = r'''import json, os, sys
raw = sys.stdin.read()
try:
    a = json.loads(raw) if raw.strip() else {}
except ValueError as e:
    print("close: ArgumentsBad stdin 不是 JSON：%s" % e, file=sys.stderr)
    print("close: ArgumentsBad stdin 不是 JSON")
    sys.exit(1)
here = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(here, "..", "..", "..", "data", "templates.json"), encoding="utf-8") as f:
    close = json.load(f)["generic"]["close"]
keys, order = sorted(close), ["借景", "動作", "留白"]
hint = a.get("hint") if isinstance(a, dict) else None
print(close[keys[(order.index(hint) if hint in order else 0) % len(keys)]]["text"])
'''
CLOSE = {"name": "close", "summary": "收尾旁白：照 hint 從 data/templates.json 的 generic.close 挑一句（同 hint 同輸出）",
         "description": "收尾旁白：給 hint（借景／動作／留白）回一行收尾旁白「（…）」，候選來自 templates.json 的 generic.close；同 hint 同輸出。",
         "parameters": {"type": "object", "properties": {"hint": {"type": "string", "description": "這份的角度：借景／動作／留白"}}, "required": []},
         "code": CLOSE_CODE}
VOICE_OLD = 'if not any(t in text for t in tics):\n    text = "%s，%s" % (tics[0], text)'
VOICE_NEW = ('idx = args.get("idx") if isinstance(args.get("idx"), int) and not isinstance(args.get("idx"), bool) else 0   # selfopt：口癖照 idx 輪替（不帶＝0＝原行為）\n'
             'if not any(t in text for t in tics):\n    text = "%s，%s" % (tics[idx % len(tics)], text)')
TOOL_OLD = '"ending": {"type": "string", "description": "句尾語氣詞，例：啦"}}'
TOOL_NEW = '"ending": {"type": "string", "description": "句尾語氣詞，例：啦"}, "idx": {"type": "integer", "description": "第幾份（口癖照它輪替；不給＝0）"}}'


def script(sub, mode):
    if mode == "cheat":
        return [("opt_describe", {}),
                ("opt_edit", {"path": "data/dims.json", "edits": [{"old_text": "\"source\"", "new_text": "\"source\" "}]}),
                ("opt_write", {"path": "proto8/tests/test_cheat.py", "content": "import unittest\n"}),
                ("opt_read", {"path": "data/bench/Q16.json"})], "（照劇本作弊）"
    if mode == "break":
        return [("opt_describe", {}),
                ("opt_edit", {"path": sub + "/_entry", "edits": [{"old_text": "import json, sys", "new_text": "import json, sys\nif True\n"}]}),
                ("opt_test", {}), ("opt_note", {"what": "改壞了 _entry", "why": "break 劇本"})], "改了 _entry（測試紅）"
    if sub == "writer":
        return [("opt_describe", {}), ("opt_history", {"max_runs": 6}), ("opt_extract", CLOSE), ("opt_test", {}),
                ("opt_note", {"what": "抽了 close：收尾旁白照 hint 從 templates.json 的 generic.close 挑", "why": "decisions_left 還有收尾旁白；收尾段固定、確定性升"})], \
            "抽了 close（收尾旁白交給工具，stage.tools 加了 close）；opt_test 綠。"
    if sub.endswith("/voice"):
        return [("opt_describe", {}), ("opt_read", {"path": sub + "/_entry"}),
                ("opt_edit", {"path": sub + "/_entry", "edits": [{"old_text": VOICE_OLD, "new_text": VOICE_NEW}]}),
                ("opt_edit", {"path": sub + "/tool.json", "edits": [{"old_text": TOOL_OLD, "new_text": TOOL_NEW}]}),
                ("opt_test", {}),
                ("opt_note", {"what": "voice 加選填參數 idx：口癖照 idx 輪替", "why": "同題三份口癖都是第一個（多樣性低）；不帶 idx 行為不變"})], \
            "voice 的口癖改成照 idx 輪替（選填、不帶＝原行為）；opt_test 綠。"
    return [("opt_describe", {}), ("opt_note", {"what": "看過，沒改", "why": "沒有劇本"})], "看過，沒改。"


def step(history, tools):
    """history（含這次的任務）、tools（腦看得到的）→ 下一則 assistant 訊息"""
    sub, mode = os.environ.get("OPTKIT_SUBTREE", ""), os.environ.get("GALTXT_FAKE_OPT", "")
    steps, final = script(sub, mode)
    since = max((i for i, m in enumerate(history) if m.get("role") == "user"), default=0)
    k = sum(len(m.get("tool_calls") or []) for m in history[since:])
    names = {t["function"]["name"] for t in tools}
    if history[-1].get("role") in ("user", "tool") and k < len(steps) and steps[k][0] in names:
        n, args = steps[k]
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_opt_%d" % (k + 1), "type": "function",
                                "function": {"name": n, "arguments": json.dumps(args, ensure_ascii=False)}}]}
    if mode == "cheat" and os.environ.get("OPTKIT_TREE"):     # 程式繞過工具直接改尺（accept 要抓）
        p = os.path.join(os.environ["OPTKIT_TREE"], "data", "dims.json")
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n")
    return {"role": "assistant", "content": final}
