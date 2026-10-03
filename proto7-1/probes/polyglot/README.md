# polyglot：不用 Python 的任務

看非 Python 程式只靠讀寫檔能不能操作這一層（S-01）。

- `talker.sh`（keep，POSIX sh，不用 jq）：每 20 ms 用 sed 讀 `tock.json`；每次 tock 寫 `progress.json`、經過掛載 `mnt/peer` 寫信；第 2 次 tock 寫 `mount-req/extra.json` 加掛 `other/box`，掛上後往那寫；第 4 次 tock 寫自己的 `ctl.json` 要求 restart。
- `spawner.sh`（bash，用 spawn 起一次）：開 `sleep 301 &`、`setsid sleep 302 &`、`( setsid sleep 303 & )`，然後被 kill。
- `ix`（inst JSON，aos-exec 跑 `sh -c … sleep 304`）、`bad`（`{"argv": []}`）。
- `pyw`（Python 對照），daemon 開 `AOS7_AUDIT=1`。

跑：`python3 proto7-1/probes/polyglot/probe.py`（約 1 秒）。

## 結果

- 做得到：sh 收 tock、寫 progress、經過宣告的掛載寫信、執行中加掛（mount-req→mount-done→`mnt/extra`）、寫自己的 ctl.json restart（結束碼 -15，新任務帶著加掛的 `mnt/extra`，keep 沒起兩份）。inst 任務拿得到 `AOS7_*`，kill 收得到 aos-exec 開在別的 session 的子程序（-15）；壞 inst 結束碼 125，錯誤進 out.log。
- tock 延遲：寫出→sh 看到中位 6～13 ms、最大 ~20 ms；輪詢花 7～9% 一核（每 20 ms 起 sed＋head＋sleep）。
- **kill 收不到雙 fork 的子程序**：`sleep 301`、`sleep 302` 被收掉，`sleep 303` 一直活著（被 init 收養、換 session，不在後代也不在群組裡）。身上還有 `AOS7_TID`，只能靠環境變數找到。
- **寫入紀錄看不到 sh**：talker 的 writes.jsonl 只有它叫的 `python3`（viapy.txt）和 aos7-run 自己寫的 pid.json／exit.json／out.log（9 筆，跟任務自己的混在一起）；sh 寫的 progress、信、ctl、mount-req 一筆都沒有（M-3）。
- 彆扭的地方：沒有「等 tock」的指令，只能輪詢；沒有 JSON 解析，靠 sed 抓 write_json 的排版（`indent=1`、一鍵一行），排版一改就壞；原子寫要自己 `printf > tmp && mv`，暫存檔會短暫出現在對方收件夾（跑過一次讀到 `sh-…json.tmp.…`）；寫信要自己跳脫字串。
- inst 任務的 stdout／stderr 預設丟 `/dev/null`，out.log 是空的，要自己在 inst 寫 `stdout`。
