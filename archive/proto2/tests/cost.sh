# cost 包：兩筆帳、字數分攤、沒單價。
test_cost_two_calls() {
  local tmp got
  tmp=$(mktemp -d)
  got=$(python3 - "$HERE" "$tmp" <<'PYEOF2'
import datetime, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import cost

root = sys.argv[2]
home = os.path.join(root, "agent")
llm = os.path.join(root, "llm")
os.makedirs(home)
os.makedirs(llm)
json.dump({"dir": llm}, open(os.path.join(home, "llm.json"), "w"))
json.dump([{"name": "paid", "price": {"input": 10, "output": 20,
           "reasoning": 30, "cached": 1}}],
          open(os.path.join(llm, "engines.json"), "w"))
state = {"step": 8, "last_usage": {"prompt_tokens": 1}}
ctx = Ctx(root, home, state)
cost.on_act(ctx, "short", {"word": "x"}, "a" * 10, 100)
cost.on_act(ctx, "long", {"word": "y"}, "b" * 30, 300)
state["step"] = 12
state["last_usage"] = {"prompt_tokens": 40, "completion_tokens": 20,
                       "completion_tokens_details": {"reasoning_tokens": 8},
                       "prompt_cache_hit_tokens": 4}
json.dump({"aos": {"engine": "paid"}},
          open(os.path.join(home, "llm-result.json"), "w"))
cost.on_idle(ctx)
day = datetime.date.today().isoformat()
rows = [json.loads(x) for x in open(os.path.join(home, "ledger", day + ".jsonl"))]
summary = json.load(open(os.path.join(home, "ledger", "summary.json")))
tool = cost.run("cost_summary", {}, ctx)
recent = cost.run("cost_recent", {"n": 1}, ctx)
print(len(rows) == 2, summary["short"]["calls"] == 1,
      summary["long"]["avg_ms"] == 300, tool["total"]["calls"] == 2,
      len(recent) == 1, all(r["args_mark"] and "word" not in r["args_mark"] for r in rows),
      state["pending_ledger"] == [])
print(rows[0]["llm_round"]["prompt_tokens"] == 10,
      rows[1]["llm_round"]["prompt_tokens"] == 30,
      rows[0]["llm_round"]["reasoning_tokens"] == 2,
      rows[1]["llm_round"]["reasoning_tokens"] == 6,
      abs(summary["short"]["total_cost"] - 0.000211) < 1e-12,
      abs(summary["long"]["total_cost"] - 0.000633) < 1e-12)
PYEOF2
)
  if [ "$(printf '%s\n' "$got" | sed -n '1p')" = "True True True True True True True" ]; then
    ok "cost：兩次工具呼叫寫兩行，summary 與查詢工具都對"
  else
    fail "cost：兩行帳或 summary 不對（$got）"
  fi
  if [ "$(printf '%s\n' "$got" | sed -n '2p')" = "True True True True True True" ]; then
    ok "cost：同一輪用量照回傳字數一比三分攤，價錢也跟著分"
  else
    fail "cost：字數分攤不對（$got）"
  fi
  rm -rf "$tmp"
}

test_cost_without_price() {
  local tmp got
  tmp=$(mktemp -d)
  got=$(python3 - "$HERE" "$tmp" <<'PYEOF2'
import datetime, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import cost

root = sys.argv[2]
home = os.path.join(root, "agent")
llm = os.path.join(root, "llm")
os.makedirs(home)
os.makedirs(llm)
json.dump({"dir": llm}, open(os.path.join(home, "llm.json"), "w"))
json.dump([{"name": "free-unknown"}], open(os.path.join(llm, "engines.json"), "w"))
state = {"step": 2, "last_usage": None}
ctx = Ctx(root, home, state)
cost.on_act(ctx, "mystery", {}, {"error": "壞掉"}, 7)
state["step"] = 6
cost.on_result(ctx, "main", "one.json", {"aos": {"engine": "free-unknown",
               "usage": {"prompt_tokens": 9, "completion_tokens": 3}}})
day = datetime.date.today().isoformat()
row = json.loads(open(os.path.join(home, "ledger", day + ".jsonl")).readline())
summary = json.load(open(os.path.join(home, "ledger", "summary.json")))
print(row["llm_round"]["cost"] is None, summary["mystery"]["total_cost"] is None,
      row["ok"] is False, row["error_kind"] == "tool_error")
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "cost：引擎沒 price 就留 null，也有成功與錯誤種類"
  else
    fail "cost：沒單價或錯誤記號不對（$got）"
  fi
  rm -rf "$tmp"
}

test_cost_two_calls
test_cost_without_price
