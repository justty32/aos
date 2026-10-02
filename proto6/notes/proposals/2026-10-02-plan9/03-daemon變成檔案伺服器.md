# 三、把 daemon 重想成一個檔案伺服器

← [提案入口](README.md)｜上一份：[Linux 上的工具](02-Linux上的工具與代價.md)｜下一份：[tick 與 inst 變成目錄](04-tick與inst變成目錄.md)

這份是**推想**，不是 Plan 9 真的有的東西。方法只有一條：現在凡是「連 socket、送一行 JSON、收一行 JSON」的地方，改成「開一個檔、寫一行字、讀一個檔」。daemon 不再開 socket，而是把自己掛成一棵目錄。

## 現在 vs 推想

| 現在（proto6） | Plan 9 式 |
|---|---|
| `aos-ctl wake a` → 連 `ctl.sock` 送 `{"wake":"a"}` | `echo wake > /aos/d/insts/a/ctl` |
| `aos-ctl status a` → 收一行 JSON | `cat /aos/d/insts/a/status` |
| `aos-mq send $DOOR '{"hi":1}'` | `echo '{"hi":1}' > /aos/d/doors/alerts` |
| `aos-mq take` → 收 `{"ok":true,"messages":[…]}` | `cat /aos/d/insts/a/inbox`（讀完即取走） |
| `aos-mq peek` | `cat /aos/d/insts/a/inbox.peek` 或 `ls /aos/d/insts/a/mail/` |
| `kill -HUP <daemon pid>`（現在拿不到 pid） | `echo reload > /aos/d/ctl` |
| `AOS_DAEMON_CTL_SOCKET`、`AOS_DAEMON_MQ_*`、`AOS_DAEMON_INST` 三組環境變數 | 只剩一個約定：「你的 daemon 掛在 `/aos/d`，你自己是 `/aos/d/self`」 |
| socket 檔 chmod 666、權限靠所在資料夾 | 檔案伺服器自己回報 uid／mode；或靠 namespace 裡「看不看得到」 |

## 檔案樹

```text
/aos/d/                          ← 一個 daemon ＝ 一棵樹（FUSE 或 9P 掛上來）
  ctl                            ← 寫：reload、shutdown
  status                         ← 讀：一行一項，固定欄位
  config                         ← 讀：展開後的設定（JSON，給人看）
  doors/
    alerts                       ← 寫＝寄信（一次 write 一封；內容是 JSON）
    team                         ← 同上；誰能寫靠 mode／namespace
  insts/
    a/
      ctl                        ← 寫：wake、wake -k、pause、resume、kill、restart
      status                     ← 讀：一行：running=0 paused=0 stopped=0 last_exit=0 next=…
      inbox                      ← 讀：取走全部信，一行一封 JSON；空＝空檔
      mail/                      ← 目錄版：一封一檔 `0001.json`，rm 即取走（peek＝ls）
      out                        ← 讀：上次 aos-exec 的 stdout（取代 exec_out_path）
      err
      wait                       ← 讀會 block 到下一次結束，回一行結束碼（Plan 9 /proc/n/wait 的作法）
    jobs/report.json/            ← inst 字面值含斜線就是子目錄，天然成立
      …
  self -> insts/a                ← 每個任務的 namespace 裡，self 指向自己那一項（bind 做的）
```

`self` 是重點：Plan 9 的 `/proc` 沒有 `self`（記憶中如此，程式用 getpid），但 Linux 有 `/proc/self`，意思一樣——**不用環境變數告訴你「你是誰」，你的 namespace 裡 `self` 就是你**。daemon 開 `aos-exec` 前把 `insts/a` bind 到 `self`（或整棵只掛 `insts/a` 當 `/aos/me`），任務裡的程式永遠寫 `/aos/me/ctl`，不用查 `AOS_DAEMON_INST`。

## ctl 的文字格式

Plan 9 的慣例是**一行一個指令、空白分隔、不是 JSON**（`/proc/n/ctl` 收 `kill`、`stop`、`pri 13`）。這裡照抄：

```text
wake
wake -s          # skip_while_running
wake -s -k       # 加 keep_schedule
pause
resume
kill
restart
```

錯誤怎麼回：Plan 9 是 `write()` 失敗、錯誤字串在 `errstr`；Linux FUSE 上就是 `write` 回 `EINVAL`／`EPERM`／`ENOENT` 加 errno。**JSON 的 `{"ok":false,"error":"stopped"}` 退化成 `write: EBUSY`**。細一點的錯誤字串可以放在 `insts/a/error`（最後一次失敗的原因），要看再 cat。這是「一行文字夠不夠」的第一個分歧點，見 [JSON 放哪](06-JSON放哪與文字格式.md)。

## status 的文字格式

```text
inst=a running=0 pending=0 paused=0 stopped=0 last_exit=0 last_end=2026-10-02T15:04:05+08:00 next=2026-10-02T15:05:05+08:00
```

一行、`key=value`、空白分隔，跟現在 daemon stdout 的那一行是同一種格式——所以其實**現行 daemon 已經在用 Plan 9 式文字**，只是放在 stdout 而不是檔案。shell 用 `cut`／`awk` 就能切，不用 `jq`。

## 信：寫檔就是寄

```sh
# 寄
printf '%s\n' '{"type":"say","text":"算 x.md 字數"}' > /aos/d/doors/team
# 收（取走）
cat /aos/me/inbox > work/in.jsonl
# 看不取
ls /aos/me/mail/
```

一次 `write()` 一封，daemon 在 FUSE 的 write handler 裡收下、放進訂戶信箱、叫醒。**信本身留 JSON**：信是結構化資料，不是指令；Plan 9 的 plumber 訊息也是多欄位的（`src`、`dst`、`wdir`、`type`、`attr`、`ndata`、data），只是用自己的文字格式，不是 JSON。這裡沒必要發明新格式，JSON 就是我們的 plumb 格式。

`mail/` 目錄版比 `inbox` 檔好的地方：取一封不用取全部、`rm` 就是 ack、`ls` 就是 peek、inotify 可以盯著它（FUSE 上 inotify 的限制見 [02](02-Linux上的工具與代價.md)）。代價：daemon 要給每封信編號、記得哪些被 rm 了。

## wait 檔：等一項結束，不用 polling

Plan 9 `/proc/n/wait` 讀了會 block 到子行程結束，回一行。這裡照抄：`cat /aos/d/insts/a/wait` 擋住直到 a 下一次跑完，回 `exit=0 ms=812`。kernel 想「叫醒 bob、等它跑完再看摘要」就是：

```sh
echo wake > /aos/d/insts/bob/ctl
cat /aos/d/insts/bob/wait        # block
cat /aos/d/insts/bob/out
```

這條在現行設計做不到（`aos-ctl wake` 送出就回，只能下一格再看）。但要小心：blocking read 在 FUSE 上要處理「讀的人被 kill」（FUSE interrupt），而且**一個 tick 裡 block 住等別人，跟「反應速度是一格」的原則打架**——它給了任務一個「在格內等」的工具，使用者得決定要不要給。

## 三個明顯的好處

1. **工具消失**：`aos-ctl`、`aos-mq` 兩支程式不用寫了，shell 內建的 `echo`、`cat`、`ls`、`rm` 就是客戶端。C++11 改寫時少兩支。
2. **環境變數消失**：C-10 那張表裡 `AOS_DAEMON_*` 三組全不用；「daemon 跑 daemon 時環境變數外漏」那個坑（agent 提案找到的）**自然消失**——內層 daemon 掛在自己的 `/aos/d`，外層的樹根本不在內層任務的 namespace 裡。
3. **權限變成「看不看得到」**：要讓 team-a 的成員不能 wake team-b 的項，就是 team-b 的 `insts/` 不出現在 team-a 任務的 namespace 裡。這比「socket 放在權限對的資料夾」更直接，而且 `ls` 就能驗證。

## 三個明顯的壞處

1. daemon 要內嵌一個 FUSE（或 9P）伺服器：Python 用 pyfuse3 幾百行；C++11 用 libfuse3 也還好，但 daemon 從「一個 while 迴圈的 cron」變成「一個檔案系統」，**跟「daemon 只是笨 cron」的方向打架**。
2. 掛載點生命週期：daemon 死了掛載點會 hang（`Transport endpoint is not connected`），要 `fusermount3 -u`；現在 socket 死了頂多 `connect` 錯。
3. 一行文字回不了結構化錯誤；要嘛接受 errno，要嘛另開 `error` 檔，要嘛 ctl 的回應改成「寫完再讀同一個 fd」（Plan 9 factotum 的 `rpc` 檔就是這樣：write 請求、read 回應）。
