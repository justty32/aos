# ok-fsm 11-14：agent-fsm 範本四條 advice 的處理紀錄

來源：使用者 11-14 專區回信 `fsm:now`；任務書 `wf/temp/ok-fsm/任務書.md`；四條出自 [wf/advices/fsm範本.md](../../../../wf/advices/fsm範本.md)。

## 現況（14:27）

| 條 | 題目 | 狀態 |
|---|---|---|
| 1 | 冷卻後重寄的請求已過 deadline（T21） | **已解，3b02a41c4** |
| 2 | goal paused 時來信沒 resume（T22） | **已解，38271da3b** |
| 3 | 蒐集員寫不了純文字檔（T23，ws_write） | **建議 1 已解，38271da3b ＋ c2eced25c**；07 的兩句頂層已放（ed5032f9b） |
| 4 | 範本預設 55 支工具 | 使用者選 A。ok-astra 施工完、我審過同意，它寄 head-tools 請放行中 |
| 4b | 提示快取只命中 29% | **補丁已進 main，7ce38e7cf**（endpoint pack 的 `session_key` 開關，預設關）。要生效還要頂層在活樹 llm-gpt 的 kernel.json 開 |
| 5 | sol 可寫範圍寫在兩份清單 | 寫檔那半 ok-onboard 做（guard 還在修洞）。shell 沙箱那半：[圖紙 03](ok-fsm-1114/03-可寫範圍一份清單-圖紙.md) Argon 審後第 2 版，**還沒動手**，等四個前置（head-core 終局、ok-sec 表態、guard 複審、head-tools 放行） |

四個 commit（38271da3b、3b02a41c4、c2eced25c、7ce38e7cf）都由 head-tools 放行、經 commit-request、沒 push，都在 16:00 前進 main，隨今晚換樹的 pin。

## 14:27 收尾核對

- 我掛的 agent：ok-fsm-sol-1、ok-fsm-sol-2 都已 `subagent rm`（stack 保留）。Claude 子 agent 一隻（架快取實驗的暫存樹），已結束。
- 我起過的 daemon 都在 `~/code/fsm-1114/cache-tree/`，三次都用 `stop.sh` 收掉；記下的 pid 249539、297266、539953 和底下的 proc 都不在了。`pgrep -af fsm-1114` 沒有東西。
- `pgrep -u "$USER" -af aos-daemon`（14:26）：指向 `~/aos-home/daemon/daemon.json` 的有 37183、210305、890651、934905、2222158；另有 37179、261661（相對路徑 daemon.json）、kf-1114 的 159076。跟開工時（37183、1623989）比，活樹那幾台的 pid 換過、也多了；我沒有對活樹的 daemon 下過任何指令，沒有一台是我起的。
- `ls -la ~/aos-home/ws/.stack/procs/repo-aos`：autoreply、claude、daemon_reply、hooks、mailbox、queue、quiet 七夾和 history.jsonl、history_removed.jsonl、hooks.json、state.json、state_flux.json、stderr.txt、tools.json，項目跟開工時一樣（大小和時間有變，是頂層自己在動）。
- 沒刪過任何檔；暫存都在 `~/code/fsm-1114/`。

## 14:22 session id 補丁

- 使用者專區回信 sessfix: tonight（01794636911420578879.447767.2549707，head-tools 驗過），頂層指定我出補丁、ok-kmsg 審。
- 補丁、測試、第二輪對照（開 82%／關 31%）、缺口都寫在 [設計稿](ok-fsm-1114/01-預設工具包-設計稿.md)「正式補丁與第二輪對照」。
- ok-kmsg 審：沒問題。head-tools 放行。commit 7ce38e7cf。

## 14:25 這一段做了什麼

- 38271da3b 補驗（head-tools 要的）：`git archive 38271da3b` 的乾淨複本，lib/tests 211 支只紅 test_observed（沒編 aos-exec），agent-fsm 139 支全過。
- 更正：先前把 `lib/agent/goal_state.py` 寫成「存檔即生效」是錯的。活樹的 lib 是複本，要等換樹（ok-kf 指出）。本線沒有動過 `~/aos-home` 任何檔。
- ws_write 補強兩次：交件前加「自己的 `$AOS_STACK`、`$AOS_CD` 也擋」（在 38271da3b 裡；這一處是放行之後才加的，head-tools 提醒以後先講再交）；之後 c2eced25c 加「鄰居的 stack、任何 `.stack` 夾也擋」（先放行才交）。
- 交 c2eced25c 時的失誤：在 zsh 裡變數沒分詞，多 claim 了兩個少了 `proto8/` 的路徑，submit 被 RequestBad 擋下，沒有 commit 出錯的東西；release 後改用 bash 重做。
- 快取對照實驗：Claude 子 agent 架暫存樹 `~/code/fsm-1114/cache-tree/` 並冒煙（每隻 2 次問腦），對照由我跑（每隻 15 次）。跑完 `stop.sh` 收掉，記下的 pid 249539、297266、297269、297270、297271 都不在了。
- 跟 ok-kmsg：它先放 `wait.py` 的 claim 讓我交，已回 hash 給它。

## 14:10 T21 驗收、第 4 條的測試對照

- T21：sol-1 交件。`wait.py` 新增 `request_deadline()`，冷卻檢查之後、`ensure_box()` 之前判斷；`test_cooldown.py` 26 支。兩隻 sol 都已 stop。
- 跟 ok-kmsg 談定：它只在 `kernel_dir()` 旁加函式、在 send 成功寫 pending 的下一行呼叫；兩段不重疊，誰先好誰先交。
- 第 4 條對照（`~/code/fsm-1114/logs/all-rel/`、`all-p4/`）：只拿掉四包，全部測試夾裡多紅的只有 `lib/agent/tests/test_cli_tools_sub.py` 的 jsonx 斷言（出處是使用者 11-13 eca-1「A」：兩個範本都掛 jsonx）。tools40:a 蓋過其中 agent-fsm 那一半，已告訴 head-tools 和 ok-astra。
- 照問腦時送出的算法量：改前 55 支 86,491 字元，改後 40 支 50,462 字元。
- 交稿：`wf/temp/ok-fsm/aos-advice/` 三份（兩份已解、一份新意見「sol 第一輪只回會照做就停」），已寄 xiaosi。

## 13:56 驗收與交件

- T22：sol-1 交件。舊複本 `test_goal.py` 27 支、agent-fsm 整夾 127 支全過；程式逐行讀過。
- T23：sol-2 的 `lib/base/ws_write`、`lib/packs/ws-write.json`、`lib/tests/test_ws_write.py` 17 支全過（執行權限我補的）；`lib/docs/02` 那一列我補的。
- 兩條搬到 main f1ef04ba0 的複本 `~/code/fsm-1114/rel` 跑全套：agent-fsm 139 支全過；lib/tests 209 支只有 1 支紅（`test_observed` 要編好的 aos-exec，乾淨複本沒有，跟改動無關）。
- 13:55 寄 head-tools 請放行，「趕不上就留下次換樹」的時刻訂 14:45。
- 知識庫的 goal 頁、packs 頁這次不放（goal 頁在 ok-astra claim 的範圍），第 4 條施工時一起補。
- sol 兩隻第一輪都只回「我會照做」就停，催一次才動手（任務書和 system 都寫了「同一回合就動手」）。收尾時投 advice。
- llm-gpt 排隊久（sol-high 只有 2 格），一隻 sol 做一張單約 20～30 分鐘。

## 13:30 分層、第 5 條、跟 ok-onboard 的界線

- 頂層分層：ok-fsm 歸工具部，部長 head-tools。回報、請示、commit 放行都找它。
- **第 5 條（頂層 13:14 加）**：sol 的可寫範圍寫在兩份清單（`guard.json` 的 `write_roots`、`shell-boxed/_metainfo.json` 的 `sandbox.ro`／`rw`），換工作區要兩邊都改。排法：寫檔守門那一半併進 ok-onboard 的 write_guard（我提三個要求：範圍單一來源、清單能被別的程式讀到、擋下訊息寫出來源）；shell 沙箱那一半等它的清單格式定了由我接，排在第 1～3 條之後。
- **跟 ok-onboard 的界線（已回，信 01794634134145528140）**：
  - 它做：write_guard、mail_guard（before_tool hook，lib/agent 新目錄）、aos-kit 的 make、check、add。
  - 我做：範本預設 pack（tools.json）、idle.py、wait.py、goal_state.py、ws-write pack。
  - 我不做：agent_def 的角色參數（按角色選包就用 kits 的覆蓋機制）、另一套路徑守門；fsm-guard 留在 wf/public，不搬進範本。
  - 所以第 4 條縮成三件：範本預設那串要不要縮（要使用者裁）、tooldef 說明分短版長版、知識庫寫明成本。comm 包（ok-board，4d207e56c）要算進去。
- ok-onboard 量的數字（照問腦時真正送出的清單算）：範本 55 支 85,725 字元，其中說明 37,021；看包 24 支 30,087，其中說明 13,760。也就是說一半以上是參數 schema，不是說明文字。
- ok-astra 的 wait.py 已進 main（313ce20ec），第 1 條可以接。
- ok-pilot 的「回答配對」設計排在我後面，以我改完的 idle.py 為底。

## 交接與派工（13:18）

- 線雜交接信：三條都沒改程式。T21 只查到事實（deadline 在 request body 的 `priority.deadline`；brain.py 不主動產生；fsm 已有 exit 11 → think）。T22 是現行設計、有測試鎖住。T23 沒動工。
- 暫存複本：`~/code/fsm-1114/src/proto8`（`git archive 424d48d49`），清環境腳本 `~/code/fsm-1114/clean.sh`，工單在 `~/code/fsm-1114/tickets/`。
- T22 實跑：`clean.sh python3 -m unittest agent-fsm/test_goal.py` → 13 支全過，其中 `test_pause_letter_does_not_resume_then_resume` 斷言「暫停中來信照收、不 resume、不提醒」。
- sol 定義 `wf/temp/ok-fsm/defs/sol`（look、change、json 三包，沒有 shell，腦 sol-high）。`ok-fsm-sol-1` 做 T22、`ok-fsm-sol-2` 做 T23，limits `{"mem_mb":1024,"files":256}`。

### 第 2 條的設計決定（ok-fsm 定）

不自動 resume，改成「提醒一次」。

- 為什麼不自動 resume：11-11 goal 的裁定裡，pause 是 agent 自己的宣告，測試也寫明「來信照收不 resume」。暫停也可能是外面的人下的（updated_by＝outside）或到上限被 aos 停的，來一封信就自動恢復會蓋掉那兩種。
- 做法：goal 是 agent 自己暫停的，暫停之後有新訊息進來（含 `[aos] new_mail:`），腦回純文字停下來，idle 就接一則 `[aos] goal: paused (理由). A message came after you paused. …`，讓腦自己決定 resume、done 或繼續等。每次暫停只提醒一次，goal.json 不動。
- 判斷只看 history 尾巴 256 KiB，不加新的狀態檔。找不到暫停那次工具呼叫（被摺掉）就不提醒。
- 沒做：eca 那邊（aos-eca-turn）不在這次範圍。

## 開工核對（13:12）

- `pgrep -u "$USER" -af aos-daemon`：活樹 37183、1623989；其餘 37179、261661、2032807、2197479、2197485、159076（kf-1114）、2138922（ok-pilot-ask-1114）、2200836、2200837（/tmp/aos-review-round）。沒有一台是 ok-fsm 起的。
- `ls -la ~/aos-home/ws/.stack/procs/repo-aos`：autoreply、claude、daemon_reply、hooks、mailbox、queue、quiet；history.jsonl、history_removed.jsonl、hooks.json、state.json、state_flux.json、stderr.txt、tools.json。

## 第 4 條的備料

### 每包的工具說明字元數（11-14 13:18，repo 工作樹的 `_tooldef.json` 檔案大小）

| 包 | 支數 | 字元 | 最大的幾支 |
|---|---:|---:|---|
| look | 6 | 8,805 | grep 2,715、glob 2,058、ls 1,651 |
| change | 5 | 3,841 | edit 1,361 |
| delete | 2 | 1,426 | |
| shell | 2 | 1,744 | |
| gadgets | 4 | 4,018 | do_task 2,621 |
| events | 2 | 8,322 | self_hook 5,111、clock_register 3,211 |
| todo | 1 | 2,449 | |
| self | 6 | 14,084 | self_history 3,343、self_tools 3,072 |
| subagent | 3 | 11,885 | subagent 5,023、agents_ctl 4,527 |
| def | 2 | 6,499 | tools_def 3,412、agent_def 3,087 |
| mailbox | 3 | 6,414 | mailbox_send 3,676 |
| goal | 1 | 2,045 | |
| json | 9 | 11,095 | |
| jsonx | 8 | 14,429 | |
| index | 1 | 2,962 | |
| 合計 | 55 | 100,018 | |

ok-onboard 早上量活樹複本是 90,723；差的約 9 千是 repo 比活樹新。

### 設計前要記得的事

- **現在的預設是使用者 11-10 親口定的**（`lib/packs/README.md` 開頭）：「預設開到第四包，想要安全就自行限制」「2.都開吧」。所以「範本預設包縮小」是改使用者的裁定，設計稿出來要寄使用者專區裁，不能只經頂層。
- ok-onboard 的 kits「看」包已經做了一種按角色選包：9 包再關 12 支，剩 24 支（`wf/workflows/dispatch/kits/gather/tools.json`）。「做」「幫」「帶」排在它的 P3。兩邊的分界要先對口。
- advice 給了三個方向：預設少掛、說明分短版長版、知識庫寫明成本。三個不互斥。
