← [入口](README.md)｜涵蓋：建議的 `.gitignore`（逐條理由）、絕對不能擋的、跟現有範本 `stack.gitignore` 的差別｜上一份 [03-實測數據](03-實測數據.md)｜下一份 [05-其他手段與衝突](05-其他手段與衝突.md)

# `.gitignore` 建議（11-06 三題已裁，範本依裁定落地）

**放哪**：每個 daemon stack 的根各放一份（`ws/.stack/.gitignore`、kernel 那台的 stack 例如試驗場的 `llm_kernel/`），跟現有範本 [`cmd/aos-agent/stack.gitignore`](../../../../cmd/aos-agent/stack.gitignore) 同一個用法——放 stack 裡只管 image、不會誤擋使用者 ws 裡自己的 `tmp/`、`lock`、`.env`。image repo 根另放一份只有一行（`ws/.trash/`）加 `.gitattributes`（`* -text`，現有 `stack.gitattributes`）。

## 建議內容（stack 根那份；★＝調查時範本沒有、這次新增）

```gitignore
# ── 必擋：只對這台、這一刻有意義 ──
**/tmp/                       # 信箱寫到一半的信；aos-post／daemon 第一圈自己建回
**/.*                         # .名.tmp、.名.<pid>.tmp、.名.<pid>、.dest.new-<pid>、.flock、.reply.lock、.stage.txt
!/.gitignore
!/.gitattributes
**/*.sock                     # eca 的 tmux socket
**/lock                       # eca 的 fcntl 鎖
**/sender.flock               # ★ aos-llm ask 的寄件人鎖
**/order.lock/                # ★ 有序信的鎖＋名牌（行程狀態，N-67 ④）
**/order.lock.releasing.*     # ★ 放鎖殘骸
# ── 可擋：醒來會自己重寫 ──
**/think/request.json         # ★ 沒 pending 時可回 think 重建；有 pending 先收原回信
/queue.json                   # ★ kernel 排隊帳（每 300 ms 重寫，重算也沒差）
/endpoints.json               # ★ kernel 從 kernel.json 推得出
**/claude/mcp.json            # ★ eca 每次起 CLI 前重寫（codex/ 同）
**/codex/mcp.json
**/tmux.conf                  # ★ eca 開畫面時重寫
**/busy.txt                   # ★ eca hook 的旗子
**/tools/run_python/main.py   # ★ 每次叫 run_python 蓋寫
/procs_ctl_mailbox/reply/     # ★ 短命指令（ctl）的回信；凍住後叫的人已不在
**/daemon_reply/              # ★ 同上（工具小格裡叫 aos-agent 時）
# ── 可擋（會失去紀錄）：只附加的 log ──
**/stderr.txt                 # 小格 log，只給人看
**/live.jsonl                 # ★ eca 的事件串流，最大的檔（一輪幾十 KB～MB）
**/turns.jsonl                # ★ eca hook 每輪一行
**/aos-mcp-logs.jsonl         # ★ aos-mcp --enable-logs
**/mailbox_warning.txt        # ★ 只留最後一封壞信
**/transcripts/               # ★ 指到 ~/.claude 的 symlink，別台是斷鏈
**/archive/                   # ★ done --keep 的歸檔信（今天沒人用；開了就是紀錄）
**/*.bad-*                    # ★ S3 壞檔留證 <名>.bad-<時間>（11-09 使用者裁：擋掉，不自動清）
```

image repo 根那份：

```gitignore
ws/.trash/                    # trash 工具丟的檔，「清垃圾桶是人的事」；擋了＝搬過去不能還原
```

## 逐條為什麼可以擋

- **必擋那段**跟現有範本一樣的理由：搬到別台全都無意義，而且名字帶 pid 或每次不同＝每次 commit 都是新檔、刪了還留在歷史裡。新增三條是盤點時找到範本漏的鎖（[01](01-盤點表.md)）。
- **可擋（重建）**：調查時各條在 [01](01-盤點表.md)／[01-續](01-續-盤點表.md) 找到「誰在醒來後第一次用前重寫」；`think/request.json` 則依後續裁定，由 wait 退回 think 重建。不擋也不會壞，只是每次凍住都多一個新 blob。
- **可擋（紀錄）**：醒來不讀；擋掉＝這份紀錄只留在原機器。要留紀錄，用 [05](05-其他手段與衝突.md) 的「log 輪替出 image」，別讓它進 image repo。實測這段是 A→B 省下最多的（[03](03-實測數據.md)）。
- `ws/.trash/`：使用者已裁「擋掉不搬」，人定期清（[README](README.md)）。

## 絕對不能擋（擋了醒來會壞或會失憶）

| 不能擋 | 擋了會怎樣 |
|---|---|
| 各層 `state.json` | `paused` 丟了：暫停中的 agent 醒來直接跑 |
| `procs_state.json`、`procs_state_procs/` | 表沒了＝整棵樹沒人醒；分檔是表的一部分（超過 100 列才有） |
| `ctl.json`、`procs_ctl.json` | 人下的指令丟了 |
| 所有信箱的 `new/`、`cur/`（含 `queue/`、`procs_ctl_mailbox/`、`think/reply/`、kernel 的 `mailbox/`） | 還沒處理的話、在途 ctl、在飛的問腦丟了；kernel 的 `cur/<uid>/` 就是在飛那題的 stack，醒來要重跑它。**所以不能寫 `**/cur/`、`**/new/`、`**/reply/` 這種寬規則** |
| `order.json` | 有序信的序號歸零，順序錯 |
| `stage.txt` | 不知道從哪格接 |
| `history.jsonl` | agent 失憶（brain 每次從它組請求） |
| `think/pending.txt` | 在飛那題的回信憑據；丟了＝原回信沒人收。即使 request 不在，有 pending 也先收原回信 |
| `tools.json`、`llm.json`（覆蓋層）、`thought.json`、`tools/agents/children.json`、`tools/thought/children/` | 工具、腦設定、子 agent 帳全丟 |
| kernel `used.json` | 額度歸零＝多花錢 |
| eca `session.txt` | 同一台醒來接不回對話 |
| 定義資料夾、ws 的成果 | 這就是 source 與外置記憶體 |

**`think/request.json` 已裁為可重建、可擋**：大小跟 history 一樣、每輪整份重寫，原本等於 history 在 git 裡存兩份。wait 在沒有 pending 且 request 不在時退 11 回 think 重組；有 pending 先收原回信，不能因此重寄。其他必須帶走的檔案照表保留。

## 跟現有範本的差別

調查時 `stack.gitignore` 的 7 條規則全保留；上列新增項包含裁定後的 `**/think/request.json`。最值錢的是 `**/live.jsonl`（eca 才有，量最大）與 `**/archive/`（萬一有人開 `--keep`）。其餘多半是小檔，擋它是為了每次 commit 不多一批無意義的新物件。
