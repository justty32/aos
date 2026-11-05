← [入口](README.md)｜涵蓋：跨電腦、stack 與 ws 進 git、另一台 git pull 續跑——要改設計的 vs 自擔風險／寫進說明的；`.gitignore`｜上一份 [03-絕對路徑盤點](03-絕對路徑盤點.md)｜下一份 [05-衝突與方向題](05-衝突與方向題.md)

# 跨電腦與 git：哪些要改設計、哪些寫進說明就好

使用者 11-05：「搬家這塊，我預期可能會搬到另一個電腦，乃至於透過git管理，我到另一台電腦做git pull」。下面每件先說它會怎麼壞，再分「要改設計」（推薦放第一）／「自擔風險／寫進說明即可」。實測依據見 [02 § 實測 E](02-image-模型.md#實測11-05wsl-tmp-拷貝)。

## 要改設計的（3 件）

| # | 事 | 怎麼壞 | 改什麼 |
|---|---|---|---|
| 1 | **絕對路徑** | 另一台使用者名／家目錄不同（`/home/guanyu` vs `/home/lorkhan`），表上每個路徑都指到不存在的地方；同一台複製則回舊位置互踩（實測 B） | [03](03-絕對路徑盤點.md)：image 裡全部相對 daemon stack；運行時變數照舊絕對 |
| 2 | **工具 bin 路徑**（kernel.json 的 `exec`、tools.json 的 `path` 指 WSL clone 的 `lib/base`） | 另一台 clone 不在同一條路徑 | 定義自帶 lib、相對定義資料夾指（[03 原則 7](03-絕對路徑盤點.md)）；aos 指令本身靠 PATH（步 0 的 install） |
| 3 | **半寫入與認領中的信**（跑著時 commit） | `tmp/` 裡的半封信、`cur/` 裡認領了沒收完的信、`.名.tmp` 暫存、daemon 正在改的表——pull 下來是一張撕一半的照片；kernel 認領中的請求 pull 到另一台等不到回信（`pending.txt` 指的信不在） | **不改程式、改流程**：image 只在睡著時存（Ctrl-C → 表寫完才退，P-36）；說明頁寫「先 Ctrl-C 再 commit」；`.gitignore` 擋 `tmp/`、`.*`（下）。想要程式保證＝`aos-daemon-ctl sleep` 全部＋daemon 退出後才 commit，就是同一件事 |

## 自擔風險／寫進說明即可（9 件）

| # | 事 | 現況 | 怎麼說 |
|---|---|---|---|
| 4 | **行程 id、`started_at_ticks`、`boot_id`** | 表與每扇 state 窗都有；另一台 boot_id 必不同＝「沒在跑」＝起、wake（實測 E 正常） | 已經正確；說明頁一句「這幾欄是上一台的，別信」 |
| 5 | **flock、socket、lock** | kernel `mailbox/.flock`（空檔，鎖本身不跟檔走）；eca `tty.sock`（socket，git 不收、cp 過去是死的）、`lock`（fcntl） | `.gitignore` 擋 `*.sock`、`.flock`、`lock`；eca 醒來畫面要重開（`aos-agent open`） |
| 6 | **時間戳** | 全部 ISO 8601 UTC 字串（`updated_at`、`sent_at`、`served_at`）、信件名稱帶時間；兩台時鐘差只影響排序顯示 | 不管 |
| 7 | **權限位（+x）** | image 裡**沒有 +x 檔**（實測 E：git 收 32 檔、0 個 755）；定義裡 `lib/base/*/_entry` 是 755、git 記得；**Windows 端 checkout 會丟 +x、`/mnt/c` 又全部 +x**（[dev-env](../../../../../wf/workflows/dev-env.md) 已寫） | 說明：只在 Linux 檔案系統 checkout；pull 完 `chmod +x` 一輪（或 `git config core.fileMode`） |
| 8 | **git 不收空資料夾** | 四個信箱的 `tmp/new/cur/`、工具小格 `tools/<名>/` 共 13 個消失（實測 E）；**全部自癒**：daemon `aos::post::init`、idle.py／wait.py `aos-post init`、aos-tools `makedirs`；aos-agent `say` 在 agent 起來前也會先建 queue | 不改；說明一句「空資料夾會掉、第一圈自己建回」 |
| 9 | **`.gitignore` 該擋什麼** | 沒有範本 | 範本（放 `ws/.stack/.gitignore` 或 ws 根）：`**/tmp/`、`**/.*`（暫存、`.flock`；但**不要**擋 `.stack` 本身）、`**/stderr.txt`、`**/*.sock`、`**/lock`；**不擋** `state.json`（`paused` 要帶著醒）、`procs_state.json`、`history.jsonl`、`queue/`、`stage.txt`、`think/`、`used.json` |
| 10 | **兩台同時跑同一份** | 檔案系統各自一份，不會真的同時；會發生的是「A 還在跑、B pull 了舊 image 也起」＝兩個世界各走各的，下次 push 撞；或「有人在跑的 ws 被 pull 蓋掉」＝活的 image 被換底 | 說明：pull 前先 Ctrl-C；同一份 image 一次只在一台醒著（跟 lisp image 一樣） |
| 11 | **sleep 前／中 commit** | sleep 中（`stopping`／SIGTERM 等 10 秒）commit＝第 3 件；sleep 前（跑著）＝同 | 同第 3 件：等 daemon 退出 |
| 12 | **CRLF、二進位** | image 全是 UTF-8 文字 JSON／jsonl／txt，沒有二進位；Windows checkout 若 `core.autocrlf=true`，`stage.txt`（aos-fsm 讀狀態名）、`pending.txt`、`_entry` shell 檔會多 `\r` | 說明：repo 放 `.gitattributes` `* -text`（或只在 Linux checkout） |

## eca（claude／codex 當 agent）跨機的特別狀況

- `session.txt` 是 claude 的 session id，對話本體在那台的 `~/.claude/projects/<cwd 雜湊>/<id>.jsonl`；另一台 `claude --resume <id>` 找不到 → cli_session 今天怎麼報要看（`CliFailed`）。**自擔／說明**：eca 的「記憶」在 CLI 那邊、不在 image；要帶走得連 `~/.claude` 那份一起搬，或接受醒來從頭開（history.jsonl 還在、看得到以前聊什麼）。
- `transcripts/*.jsonl` 是指到 `~/.claude/...` 的 symlink：git 收 symlink（目標字串），另一台是斷鏈；無害。
- `.gitignore` 加 `**/transcripts/`、`**/session.txt`？——**不推薦擋 `session.txt`**：同一台 pull 回來還能接；斷了 cli_session 自己報。

## 對四步流程的影響

這一章沒有新增第五步：`.gitignore`／`.gitattributes` 是一次性的檔；「先 Ctrl-C 再 commit」是存 image 的習慣，不是啟動步驟。
