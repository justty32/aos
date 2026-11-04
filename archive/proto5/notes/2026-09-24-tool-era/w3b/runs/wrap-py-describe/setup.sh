#!/bin/bash
# wrap-py --describe-with-llm 對照：開 daemon＋kernel、做兩個包（機械版／模型版描述）、兩個 agent 各裝一個。
# 跑法（在 repo 根目錄）：bash proto5/notes/2026-09-24-tool-era/w3b/runs/wrap-py-describe/setup.sh
# 需要：LiteLLM http://localhost:4000/v1 的 deepseek-chat。停機：aos down（見 run.sh 最後）。
set -e
REPO=$(cd "$(dirname "$0")/../../../../../.." && pwd)
P=$REPO/proto5
HERE=$P/notes/2026-09-24-tool-era/w3b/runs/wrap-py-describe
W=${W:-$HOME/tmp/w3b-wrap}
export PATH=$P/cli:$PATH AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K PYTHONDONTWRITEBYTECODE=1
aos down >/dev/null 2>&1 || true
rm -rf "$W"; mkdir -p "$W/packs"
cat > "$W/llm.json" <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > "$W/kernel.json" <<EOF
{"pools": {"default": {"count": 2}, "llm": {"count": 2, "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
aos-kernel init --config "$W/kernel.json" >/dev/null && aos up >/dev/null
FIX=$P/lib/test/fixtures/wrapcli/opaque_funcs.py
cd "$W/packs"
# 機械版：描述＝函式名
aos-agent tools wrap-py "$FIX" --name opq_mech
# 模型版：提案（叫模型一次）→ 原樣套用（等於人看過沒改）
if [ -n "$PROPOSAL" ]; then cp "$PROPOSAL" "$W/packs/opq_llm.describe.json"; else
  AOS_LLM_CONFIG=$W/llm.json aos-agent tools wrap-py "$FIX" --name opq_llm --describe-with-llm
fi
cp "$W/packs/opq_llm.describe.json" "$HERE/proposal.describe.json"
aos-agent tools wrap-py "$FIX" --name opq_llm --describe "$W/packs/opq_llm.describe.json"
for v in mech llm; do
  aos-agent tools test "./opq_$v" | tail -1
  aos-agent init --target "$W/a-$v" >/dev/null
  rm -f "$W/a-$v/tools/date.json"          # 預設只有 date；拿掉，工具表只剩這個包（也沒有 base，免得模型寫 bash 繞過）
  aos-agent persona set "你是繁體中文助理，回答簡短。" --target "$W/a-$v" >/dev/null
  aos-agent tools add "./opq_$v" --target "$W/a-$v" >/dev/null
  cp "$HERE/notes.txt" "$W/a-$v/workspace/notes.txt"
  aos-agent tools ls --target "$W/a-$v"
done
