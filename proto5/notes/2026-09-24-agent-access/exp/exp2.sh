#!/bin/bash
# 實驗 2：base 工具包（別隊 worktree 的快照）＋ bwrap。先跑 exp1.py 建目錄。
S=$(cd "$(dirname "$0")" && pwd)
T=$S/amy-tools-base
printf '{"root": "%s"}\n' "$S/ws-A" > "$T/config.json"
cd "$S/amy" || exit 1                       # aos-agent 給工具的 cwd＝agent 家

echo '== 2a read 工具：../amy、符號連結、絕對路徑'
for p in '../amy/secret.txt' 'sneaky/secret.txt' "$S/amy/secret.txt" 'a.txt'; do
  printf '%s -> ' "$p"; printf '{"path": "%s"}' "$p" | python3 "$T/read" | tail -1 | sed "s#$S#\$S#g"
done

echo '== 2b bash 工具（沒有隔離）：'
for c in 'pwd' 'cat ../amy/secret.txt' 'cat sneaky/secret.txt' "cat $S/amy/secret.txt" 'echo K=$AOS_KERNEL_HOME KEY=$OPENAI_API_KEY'; do
  printf '%s -> ' "$c"; printf '{"command": "%s"}' "$c" | AOS_KERNEL_HOME=/x/K OPENAI_API_KEY=sk-demo python3 "$T/bash" | head -1 | sed "s#$S#\$S#g"
done

echo '== 2c bwrap 可用嗎'
command -v bwrap && bwrap --version
J=(bwrap --unshare-all --die-with-parent --new-session
   --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib /lib64 --symlink usr/bin /sbin
   --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp
   --bind "$S/ws-A" /ws --chdir /ws
   --clearenv --setenv PATH /usr/bin --setenv HOME /ws)
for c in 'pwd' 'ls' 'cat a.txt' 'cat ../amy/secret.txt' 'cat sneaky/secret.txt' "cat $S/amy/secret.txt" 'ls /home' 'echo K=$AOS_KERNEL_HOME KEY=$OPENAI_API_KEY' 'echo hi > new.txt && echo wrote' 'curl -sS -m 3 http://localhost:4000 >/dev/null && echo net-ok || echo net-blocked'; do
  printf '%s -> ' "$c"; AOS_KERNEL_HOME=/x/K OPENAI_API_KEY=sk-demo "${J[@]}" bash -c "$c" 2>&1 | head -1 | sed "s#$S#\$S#g"
done
ls "$S/ws-A"
rm -f "$S/ws-A/new.txt"

echo '== 2d 換成 ws-B：只改 bind 的來源，工具裡看到的還是 /ws'
"${J[@]/$S\/ws-A/$S/ws-B}" bash -c 'pwd; ls' 2>&1 | tr '\n' ' '; echo

echo '== 2e bwrap 開一次多久（10 次平均）'
python3 - "${J[@]}" <<'EOF'
import subprocess, sys, time
cmd = sys.argv[1:] + ['true']
t = time.time()
for _ in range(10):
    subprocess.run(cmd, check=True)
print('%.1f ms' % ((time.time() - t) * 100))
EOF

echo '== 2f 外面開好的 stdin/stdout 能穿過 bwrap（aos-exec 的重導向在 bwrap 之外）'
echo '{"command": "cat a.txt"}' > "$S/in.json"
"${J[@]}" --ro-bind "$T" /opt/tools --setenv AOS_ROOT /ws bash -c 'cat' < "$S/in.json" > "$S/out.txt"; cat "$S/out.txt"
