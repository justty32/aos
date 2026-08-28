#!/bin/bash
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh

echo "===== X-1 header .temp 被佔住（目錄）→ HeaderWriteFailed，批照發、去重失效 ====="
W=$LAB/wx1; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
mkdir "$W/.aos/inst-head.json.temp"
printf '%s\n' '[{"argv":["/bin/sh","-c","echo R >> '"$LOG"'"]}]' > "$W/.aos/inst.tempd/1000-0.json"
chmod 500 "$W/.aos/inst.tempd"     # 讓投遞刪不掉，模擬「發布成功但沒清乾淨」
"$AOS" exec "$W" 2>&1 | sed 's/^/  /'; echo "  rc=$?"
echo "  log: [$(tr '\n' ',' < "$LOG")]"
echo "  .aos: [$(ls -A "$W/.aos" | tr '\n' ' ')]"
echo "  --- 第二回合（同一份投遞還在，沒有 header 可比對）---"
"$AOS" exec "$W" 2>&1 | sed 's/^/  /'
echo "  log: [$(tr '\n' ',' < "$LOG")]  ← 有兩個 R 就是重複執行"
"$AOS" exec "$W" >/dev/null 2>&1
echo "  第三回合後 log: [$(tr '\n' ',' < "$LOG")]"
chmod 700 "$W/.aos/inst.tempd"

echo
echo "===== X-2 版面元件型別錯亂 ====="
tc() { echo "  -- $1 --"; timeout 8 "$AOS" exec "$2" 2>&1 | head -2 | sed 's/^/     /'; timeout 8 "$AOS" exec "$2" >/dev/null 2>&1; echo "     exec rc=$?"; }
W=$LAB/wx2a; mkworld "$W"; rmdir "$W/.aos/inst.tempd"; echo x > "$W/.aos/inst.tempd"
tc "inst.tempd 是檔案" "$W"
W=$LAB/wx2b; mkworld "$W"; mkdir "$W/.aos/inst.json"
tc "inst.json 是目錄" "$W"
W=$LAB/wx2c; mkworld "$W"; mkdir "$W/.aos/inst.json.runi"
tc "inst.json.runi 是目錄" "$W"
W=$LAB/wx2d; mkworld "$W"; mkdir "$W/.aos/turn"
printf '%s\n' '[{"argv":["/bin/true"]}]' > "$W/.aos/inst.tempd/1000-0.json"
tc "turn 是目錄" "$W"
W=$LAB/wx2e; mkworld "$W"; ln -s /nonexistent "$W/.aos/inst.json"
printf '%s\n' '[{"argv":["/bin/true"]}]' > "$W/.aos/inst.tempd/1000-0.json"
tc "inst.json 是斷掉的 symlink（lstat 看得到、read 讀不到）" "$W"
ls -la "$W/.aos"

echo
echo "===== X-3 SIGKILL 中途 → .runi 殘留 → 之後永遠拒絕（§D-7 設計如此，確認後果）====="
W=$LAB/wx3; mkworld "$W"; LOG=$W/run.log; : > "$LOG"
printf '%s\n' '[{"argv":["/bin/sh","-c","sleep 5; echo DONE >> '"$LOG"'"]}]' | "$AOS" deliver "$W" >/dev/null
"$AOS" exec "$W" & E=$!
sleep 1; kill -9 $E; wait $E 2>/dev/null
echo "  .aos: [$(ls -A "$W/.aos" | tr '\n' ' ')]"
"$AOS" exec "$W" 2>&1 | sed 's/^/  /'; echo "  rc=$?"
sleep 5
echo "  子行程有沒有變孤兒繼續跑完: log=[$(tr '\n' ',' < "$LOG")]"
echo "  turn=$(cat "$W/.aos/turn")"

echo
echo "===== X-4 aos deliver 的檔名重複率（15c 的觸發前提：pid 重用）====="
W=$LAB/wx4; mkworld "$W"
for i in $(seq 1 600); do printf '%s\n' '[{"argv":["/bin/true"]}]' | "$AOS" deliver "$W" 2>/dev/null; done > "$LAB/names.txt"
grep -o '"delivery":"[^"]*"' "$LAB/names.txt" | sed 's/.*:"//;s/"//' > "$LAB/names2.txt"
echo "  600 次投遞，唯一檔名 $(sort -u "$LAB/names2.txt" | wc -l) 個"
echo "  重複的檔名: $(sort "$LAB/names2.txt" | uniq -d | tr '\n' ' ')"
echo "  pid 範圍: $(sort -t- -k1 -n "$LAB/names2.txt" | head -1) .. $(sort -t- -k1 -n "$LAB/names2.txt" | tail -1)"
echo "  /proc/sys/kernel/pid_max = $(cat /proc/sys/kernel/pid_max)"
