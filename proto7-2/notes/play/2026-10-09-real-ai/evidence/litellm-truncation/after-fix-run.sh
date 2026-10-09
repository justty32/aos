#!/usr/bin/env bash
set -u
P=/home/lorkhan/repo/simple_tools/aos-wt/MC/proto7-2
N=/tmp/mc_replay/node
rm -rf "$N"; mkdir -p "$N/.aos" "$N/budget/llm"
cp "$P/packs/llmcall/examples/litellm/grant.json" "$N/budget/llm/grant.json"
printf '%s\n' '{"round":5,"open":false}' > "$N/.aos/round.json"
cd "$N"
python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm &
LP=$!
trap 'kill $LP 2>/dev/null; wait $LP 2>/dev/null' EXIT
sleep 1
python3 "$P/packs/budget/bin/aos7-budget" init budget/llm >/dev/null
for c in orig-1:req-orig orig-2:req-orig orig-3:req-orig orig-4:req-orig direct-1:req-direct direct-2:req-direct; do
  id=${c%%:*}; rq=${c#*:}
  python3 "$P/packs/llmcall/bin/aos7-llmcall" call budget/llm --holder author --call "$id" --request /tmp/mc_replay/$rq.json --reserve 1000000 --deadline 900 > /tmp/mc_replay/$id.receipt.json 2>/tmp/mc_replay/$id.err
  echo "$id rc=$?"
done
