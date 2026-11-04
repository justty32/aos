# sched：priority 物件、每格重排、分帳與 ls。

# 1. write_request 接 priority 物件，也把 requester 放在頂層供帳本使用。
TMP=$(mktemp -d); prep_llm "$TMP/llm"
WROTE=$(PYTHONDONTWRITEBYTECODE=1 python3 - "$HERE" "$TMP/llm" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import aos_llm
name = aos_llm.write_request(
    sys.argv[2], {"messages": []}, priority={"level": 3},
    requester="team-a/alice", kind="tool", deadline="2099-01-01T00:00:00+00:00",
    name="sched-write.json")
d = json.load(open(os.path.join(sys.argv[2], "requests", name), encoding="utf-8"))
print("%s %s %s %s" % (d["requester"], d["priority"]["requester"],
                         d["priority"]["kind"], d["priority"]["level"]))
PYEOF2
)
if [ "$WROTE" = "team-a/alice team-a/alice tool 3" ]; then
  ok "sched：write_request 寫 priority 物件與 requester"
else
  fail "sched：write_request 寫錯：$WROTE"
fi
rm -rf "$TMP"

# 2. 舊數字和新物件混排，分數高的先開。
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"priority": 6, "messages": []}' > "$TMP/llm/requests/number.json"
echo '{"priority": {"level": 5, "kind": "chat", "requester": "b/bob"}, "messages": []}' > "$TMP/llm/requests/object.json"
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launch number.json"*"queued 1"*) ok "sched：數字與物件照同一個分數混排" ;;
  *) fail "sched：數字物件混排不對：$OUT" ;;
esac
kill_workers "$TMP/llm"; rm -rf "$TMP"

# 3. deadline 已過期時，不管一般分數多低都先開。
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"priority": {"level": 0, "kind": "background", "deadline": "2000-01-01T00:00:00+00:00"}, "messages": []}' > "$TMP/llm/requests/late.json"
echo '{"priority": {"level": 9, "kind": "chat"}, "messages": []}' > "$TMP/llm/requests/high.json"
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launch late.json"*"queued 1"*) ok "sched：過期 deadline 插到未過期請求前面" ;;
  *) fail "sched：deadline 沒插隊：$OUT" ;;
esac
kill_workers "$TMP/llm"; rm -rf "$TMP"

# 4. 等夠久最多加 300，低 level 也能離開隊尾。
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"priority": {"level": 0, "kind": "chat", "age_boost": 1}, "messages": []}' > "$TMP/llm/requests/old.json"
touch -d '6 hours ago' "$TMP/llm/requests/old.json"
echo '{"priority": {"level": 2, "kind": "chat"}, "messages": []}' > "$TMP/llm/requests/new.json"
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launch old.json"*"score=330"*) ok "sched：age_boost 讓久等請求不會餓死" ;;
  *) fail "sched：age_boost 不對：$OUT" ;;
esac
kill_workers "$TMP/llm"; rm -rf "$TMP"

# 5. 同 level 時 kind 是 chat、tool、think、background。
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
for K in chat tool think background; do
  printf '{"priority": {"level": 1, "kind": "%s", "requester": "%s/x"}, "messages": []}\n' "$K" "$K" > "$TMP/llm/requests/$K.json"
done
SEQ=$(llm_pump "$TMP/llm" | sed -n 's/.*launch \(chat\|tool\|think\|background\)\.json .*/ \1/p' | tr -d '\n')
if [ "$SEQ" = " chat tool think background" ]; then
  ok "sched：kind 分數會改變開工順序（$SEQ）"
else
  fail "sched：kind 順序不對：$SEQ"
fi
rm -rf "$TMP"

# 6. 同一格每開一筆就重算近期占用，別的集團會插進來。
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 3}]"
echo '{"priority": {"level": 1, "kind": "chat", "requester": "a/one"}, "messages": []}' > "$TMP/llm/requests/a1.json"
sleep 0.02
echo '{"priority": {"level": 1, "kind": "chat", "requester": "a/two"}, "messages": []}' > "$TMP/llm/requests/a2.json"
echo '{"priority": {"level": 1, "kind": "tool", "requester": "b/one"}, "messages": []}' > "$TMP/llm/requests/b.json"
SEQ=$(llm_tick "$TMP/llm" | sed -n 's/.*launch \(a1\|a2\|b\)\.json .*/ \1/p' | tr -d '\n')
if [ "$SEQ" = " a1 b a2" ]; then
  ok "sched：每次開工後更新 recent 再重排（$SEQ）"
else
  fail "sched：recent 沒在同一格重排：$SEQ"
fi
kill_workers "$TMP/llm"; rm -rf "$TMP"

# 7. 新帳本同時按模型與 requester 累加。
TMP=$(mktemp -d); prep_llm "$TMP/llm"; DAY=$(date +%Y-%m-%d)
mkdir -p "$TMP/llm/usage/pending"
printf '{"day":"%s","key":"base|m","requester":"team/a","usage":{"total_tokens":7},"error":false,"took_ms":3}\n' "$DAY" > "$TMP/llm/usage/pending/one.json"
llm_tick "$TMP/llm" >/dev/null
U=$(llm_field "$TMP/llm/usage/$DAY.json" '"%s %s" % (d["by-model"]["base|m"]["total_tokens"], d["by-requester"]["team/a"]["total_tokens"])')
if [ "$U" = "7 7" ]; then
  ok "sched：usage 有 by-model 與 by-requester 兩層"
else
  fail "sched：usage 兩層不對：$U"
fi
rm -rf "$TMP"

# 8. usage CLI 讀得懂舊平鋪檔。
TMP=$(mktemp -d); prep_llm "$TMP/llm"; DAY=1999-01-02
mkdir -p "$TMP/llm/usage"
echo '{"old-base|old-model": {"requests": 2, "total_tokens": 11}}' > "$TMP/llm/usage/$DAY.json"
OUT=$("$LLM" usage "$DAY" --dir "$TMP/llm" 2>&1)
case "$OUT" in
  *"按模型"*"old-base|old-model"*"11"*"按 requester"*) ok "sched：usage CLI 相容舊平鋪帳本" ;;
  *) fail "sched：舊帳本讀不懂：$OUT" ;;
esac
rm -rf "$TMP"

# 9. ls 印分數、短理由、requester 與過期標記。
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"priority": {"level": 5, "kind": "chat", "requester": "team/alice", "deadline": "2000-01-01T00:00:00+00:00"}, "messages": []}' > "$TMP/llm/requests/show.json"
OUT=$("$LLM" ls --dir "$TMP/llm" 2>&1)
case "$OUT" in
  *"show.json"*"score=530"*"level=5 chat +40"*"normal=-10"*"requester=team/alice"*"deadline=late"*)
    ok "sched：ls 顯示分數與理由" ;;
  *) fail "sched：ls 理由不完整：$OUT" ;;
esac
rm -rf "$TMP"
