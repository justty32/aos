#!/bin/sh
# polyglot 的 sh 任務：只靠讀寫檔操作 aos 這一層（S-01）。沒有 Python、沒有 jq。
# 每收到一次 tock：寫 progress.json、經過掛載點 mnt/peer 寫一封信；
# 第 2 次 tock 寫加掛請求 mount-req/extra.json，掛上後也往 mnt/extra 寫；
# 第 1 次 tock 叫一次 python3 寫檔（看寫入紀錄只記得到哪一段）；
# 第 4 次 tock 且自己不是 restart 來的：寫自己的 ctl.json 要求 restart。
T="$AOS7_TASK"
last=0
n=0
restarted=1
grep -q '"restart_of": null' "$T/birth.json" && restarted=0

# 原子寫：先寫暫存檔再 mv（同一資料夾內 rename）
put() { printf '%s\n' "$2" > "$1.tmp.$$" && mv -f "$1.tmp.$$" "$1"; }
# 從 aos 寫的 JSON 抓 "round" 的數字：靠 write_json 的排版（indent=1，一個鍵一行），換排版就壞
round_of() { sed -n 's/.*"round": *\([0-9][0-9]*\).*/\1/p' "$1" 2>/dev/null | head -n 1; }
at_of() { sed -n 's/.*"at": *"\([^"]*\)".*/\1/p' "$1" 2>/dev/null | head -n 1; }

while :; do
  r=$(round_of "$T/tock.json")
  r=${r:-0}
  if [ "$r" -gt "$last" ]; then
    last=$r
    n=$((n + 1))
    put "$T/progress.json" "{\"round\": $r, \"n\": $n, \"seen_ns\": $(date +%s%N), \"tock_at\": \"$(at_of "$T/tock.json")\", \"restarted\": $restarted}"
    put "$T/mnt/peer/sh-$AOS7_TID-$r.json" "{\"from\": \"$AOS7_NODE_ID\", \"round\": $r, \"body\": \"hi from sh\"}"
    if [ $n -eq 1 ]; then
      python3 -c "import os; open(os.path.join(os.environ['AOS7_TASK'], 'viapy.txt'), 'w').write('py')"
    fi
    if [ $n -eq 2 ] && [ ! -e "$T/mnt/extra" ]; then
      mkdir -p "$T/mount-req"
      put "$T/mount-req/extra.json" '{"name": "extra", "path": "other/box", "why": "sh 想寫 other/box"}'
    fi
    if [ -d "$T/mnt/extra" ]; then
      put "$T/mnt/extra/sh-$AOS7_TID-$r.json" "{\"round\": $r}"
    fi
    if [ $n -eq 4 ] && [ $restarted -eq 0 ]; then
      put "$T/ctl.json" "{\"op\": \"restart\", \"by\": \"$AOS7_NODE_ID:$AOS7_TID\", \"why\": \"sh 自己要求\"}"
    fi
  fi
  sleep 0.02
done
