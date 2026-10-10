#!/usr/bin/env bash
set -u
P=/home/lorkhan/repo/simple_tools/aos-wt/MN2/proto7-2
REQ=$P/packs/author/examples/aos-tool-mailcount/request.json
k=$1
N=/home/lorkhan/repo/simple_tools/aos-wt/MN2.smoke/v3-luna-$k
mkdir -p "$N/.aos" "$N/budget/llm"
printf '%s\n' '{"round":5,"open":false}' > "$N/.aos/round.json"
cat > "$N/budget/llm/grant.json" <<'J'
{"v":1,"grant":"menu-try","budget":"llm","holder":"author","resource":"llm.tokens","gateway":"llm.litellm","amount":3000000,"clock":"completed_tock","from":0,"until":1000000,"delegate":false}
J
cd "$N" || exit 2
python3 "$P/packs/budget/bin/aos7-budget" init budget/llm > init.stdout 2> init.stderr
init_rc=$?
if [ "$init_rc" -ne 0 ]; then echo "init rc=$init_rc"; cat init.stderr; exit "$init_rc"; fi
python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm > ledger.stdout 2> ledger.stderr &
ledger_pid=$!
cleanup(){ kill "$ledger_pid" 2>/dev/null || true; wait "$ledger_pid" 2>/dev/null || true; }
trap cleanup EXIT
sleep 1
python3 "$P/packs/menu/examples/aos-tool/build.py" brief "$REQ" > brief.txt 2> brief.stderr
brief_rc=$?
start=$(date +%s)
cmd=(systemd-run --user --scope -q -p TasksMax=300 env AOS7_AOS_TOOL_NO_SCOPE=1 python3 -B "$P/packs/menu/bin/aos7-menu" run "$N" "$P/packs/menu/examples/aos-tool/menu.json" --llm chatgpt-gpt-6-luna --var name=mailcount --var request="$REQ" --var review=chatgpt-gpt-6-astra-high --brief "$N/brief.txt")
"${cmd[@]}" > run1.stdout 2> run1.stderr
rc=$?
printf '%s\n' "$rc" > run1.rc
if [ "$rc" -eq 3 ]; then
  "${cmd[@]}" > run2.stdout 2> run2.stderr
  rc=$?
  printf '%s\n' "$rc" > run2.rc
fi
end=$(date +%s)
printf '%s\n' "$((end-start))" > elapsed.seconds
python3 -B "$P/packs/menu/bin/aos7-menu" status "$N" > status.stdout 2> status.stderr
python3 "$P/packs/budget/bin/aos7-budget" status budget/llm > budget-status.stdout 2> budget-status.stderr
printf 'run_rc=%s elapsed_seconds=%s\n' "$rc" "$((end-start))"
cat status.stdout
cat budget-status.stdout
