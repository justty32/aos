#!/bin/bash
# 實驗 3：(a) 開放 amy 自己但設定檔蓋成唯讀；(b) 現在的 info.json tools 能不能用 $ref 共用檔／改名。
S=$(cd "$(dirname "$0")" && pwd)
echo '{"ws": "x"}' > "$S/amy/access.json"
J=(bwrap --unshare-all --die-with-parent --new-session
   --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib /lib64
   --proc /proc --dev /dev --tmpfs /tmp
   --dir /work --bind "$S/ws-A" /work/ws --bind "$S/amy" /work/self
   --ro-bind "$S/amy/access.json" /work/self/access.json --ro-bind "$S/amy/info.json" /work/self/info.json
   --chdir /work --clearenv --setenv PATH /usr/bin)
echo '== 3a 自己可寫、設定檔唯讀'
for c in 'ls' 'cat ws/a.txt' 'echo n > self/note.txt && echo note-ok' 'echo "{}" > self/access.json' 'rm self/info.json' 'mv self/access.json self/x'; do
  printf '%s -> ' "$c"; "${J[@]}" bash -c "$c" 2>&1 | tr '\n' ' '; echo
done
cat "$S/amy/access.json"; rm -f "$S/amy/note.txt"

echo '== 3b info.json 的 tools 元素用 $ref／$opt'
mkdir -p "$S/amy/tools" "$S/amy/prompts"
cat > "$S/util-tools/bash-edit-a.json" <<'EOF'
[{"type": "function", "function": {"name": "bash-edit-a", "parameters": {"type": "object"}}, "_meta": {"argv": ["true"]}}]
EOF
cd /home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-ac1cb383e848a770e/proto5/lib || exit 1
for tools in '["../util-tools/bash-edit-a.json"]' '[{"$ref": "../util-tools/bash-edit-a.json"}]' '[{"$opt": {"as": "edit-a"}, "$val": "../util-tools/bash-edit-a.json"}]'; do
  printf '{"_metainfo":{"_type":"llm_agent","_version":1},"llm":{"model":"m"},"tools":%s}\n' "$tools" > "$S/amy/info.json"
  printf 'tools=%s -> ' "$tools"
  python3 - "$S/amy" <<'EOF'
import sys
sys.path.insert(0, '.')
import aos_agent_info as ai
try:
    info = ai.load(sys.argv[1])
    names = [t['function']['name'] for t in info['tools_raw']]
    print('OK 模型看到的工具名:', names)
except Exception as e:
    print('ERR', getattr(e, 'code', type(e).__name__), str(e)[:90])
EOF
done
printf '{"_metainfo":{"_type":"llm_agent","_version":1}}\n' > "$S/amy/info.json"
