#!/bin/sh
# demo.sh - 用假腦把 galtxt-b 端到端跑一遍：q01 一稿過、q08 第 1 稿故意寫壞被打回再寫（GALTXT_FAKE_BAD_FIRST=1）、q01 再跑一次走 writer 自檢（GALTXT_FAKE_LINT=1）
# 用法：sh proto8/topdown/galtxt-b/demo.sh [工作區]   （沒給＝mktemp；要接真腦就先 export AOS_BRAIN_URL=http://localhost:4000/v1）
set -e
here=$(cd "$(dirname "$0")" && pwd)
proto8=$(cd "$here/../.." && pwd)
for p in aos-exec aos-loop aos-fsm; do
    [ -x "$proto8/impls/$p/bin/$p" ] || { echo "demo.sh: $p 還沒建（$proto8/impls/$p/bin/）；先照 wf/workflows/testing.md 建 impls" >&2; exit 1; }
    PATH="$proto8/impls/$p/bin:$PATH"
done
export PATH
ws=${1:-$(mktemp -d)}
mkdir -p "$ws/new"
cp "$here/examples/q01_河鹿堂讓書.json" "$ws/new/"
echo "== 1. q01（一稿過）  工作區 $ws"
aos-exec --ws "$ws" "$here"; echo "結束碼 $?"
echo "-- out/q01_河鹿堂讓書/answer.txt"; cat "$ws/out/q01_河鹿堂讓書/answer.txt"
echo "-- score.json"; cat "$ws/out/q01_河鹿堂讓書/score.json"
echo
echo "== 2. q08（第 1 稿故意寫壞 → check 打回 → 第 2 稿過）"
cp "$here/examples/q08_河鹿堂進新書日.json" "$ws/new/"
GALTXT_FAKE_BAD_FIRST=1 aos-exec --ws "$ws" "$here"; echo "結束碼 $?"
echo "-- out/q08_河鹿堂進新書日/answer.txt"; cat "$ws/out/q08_河鹿堂進新書日/answer.txt"
echo "-- check.json 的 history（每稿的違規）"
python3 -c "import json,sys; h=json.load(open(sys.argv[1]))['history']; [print('第 %d 稿：%d 條違規 %s' % (x['attempt'], len(x['violations']), [v['rule'] for v in x['violations']])) for x in h]" "$ws/out/q08_河鹿堂進新書日/check.json"
echo "-- score.json"; cat "$ws/out/q08_河鹿堂進新書日/score.json"
echo "-- measure.json（這題的實跑數字）"; cat "$ws/out/q08_河鹿堂進新書日/measure.json"
echo
echo "== 3. q01 再一次，writer 交稿前先叫 lint 自檢（GALTXT_FAKE_LINT=1）"
cp "$here/examples/q01_河鹿堂讓書.json" "$ws/new/q01_自檢.json"
GALTXT_FAKE_LINT=1 aos-exec --ws "$ws" "$here"; echo "結束碼 $?"
echo "-- writer 的 history（每則的 role；tool_calls→tool→answer）"
python3 -c "import json,sys; [print(m['role'], '(tool_calls %s)' % [c['function']['name'] for c in m['tool_calls']] if m.get('tool_calls') else '') for m in map(json.loads, open(sys.argv[1]))]" "$ws/.stack/writer/history.jsonl"
echo "-- measure.json 的 counter_lint_calls：$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['counter_lint_calls'])" "$ws/out/q01_自檢/measure.json")"
echo
echo "== stack 樹＝呼叫樹（P-38）"
find "$ws/.stack" -maxdepth 3 | sort
echo "== fsm trace（頂層每格一行）"
cat "$ws/.stack/trace.jsonl"
