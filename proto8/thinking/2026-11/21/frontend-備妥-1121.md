aos-frontend 備妥（線 top-1121-frontend）：乾淨複本試跑全過，今天的 hook 新格式沒弄壞前端；修一處之前就有的「寄信給沒信箱的 agent 失敗」、測試少傳一個變數，網頁 v2 已 build 在工作樹；今晚起法、大修盤點、代定事項在下面。

← [2026-11-21](README.md)

## 使用者原話與頂層的讀法

- 使用者 11-21 15:00 左右（逐字）：「然後aos frontend也幫我準備好，能先動工的就先動工。」前情：「我應該晚上會自己來玩aos，所以這邊要請你幫忙準備各種東西」「幫我把該準備的準備好」。
- 頂層的讀法（他不在、頂層代定）：「準備好」＝今晚他起樹之後前端起得來、看得到他的 agent、能對 agent 說話、不因今天的改動壞掉；「能先動工的就先動工」＝今天的改動弄壞或弄舊的地方現在修（實作層級）；大修大重構是方向題、不動工，只列「大修若要開始可以先動的小塊、各卡在哪個決定」；三個小毛病（11-18 他說「先留着」）不修。
- 我照這個讀法做，沒有不同的讀法。

## 試跑（家機，乾淨複本 `85694d214`，`~/.aos/scratch/top-1121-frontend/`）

| 項 | 結果 |
|---|---|
| `git archive HEAD` → 複本 `install.py` | 退 0，30 支指令、py 597 檔 |
| 起樹（start-api：`aos-exec root`、llm kernel、假腦 ann） | 表上 `_clock`、`_sweeper`、`llm`、`ann` 都 running；ann 回 `FAKE ANSWER to: hello …` |
| 起前端 `AOS_DAEMON=<樹>/.stack aos-frontend --port 18767 --home <暫存 view home> serve`（`config.json` 的 `ui_ports` 指 18768，避開活樹的 8767／8768） | 起得來 |
| GET `/`、`/classic`、`/agent?name=ann` 與 `/api/` 十五支 | `/` 303 轉 `/classic`（11-18 那個小毛病，照留）；其餘 200；`/api/ui-state` 不帶 key 回 400 `KeyBad`（本來就這樣）；樹上看得到 ann、llm、`_clock`、`_sweeper`、LiteLLM |
| POST `/api/say` 對 ann 說「4+5?」 | 送出，ann 回 `FAKE ANSWER to: [使用者經全景頁] 4+5? …`，`/api/agent`、`/api/thread`（delivery `read`）都看得到 |
| POST `/api/mail`、`/api/order` | **改前失敗**：`MailboxMissing mailbox not found: <樹>/.stack/procs/ann/mailbox`（見「修了哪些」）；改後兩封都進 ann 的 `mailbox/new/`，一分鐘內 mail_notify 叫醒 ann（history 多一則 `[aos] new_mail: 2 new letters from user …`） |
| POST `/api/board` | 成 |
| POST `/api/compact`、`/api/slash` `/compact` | 回「ann 不是這個指令支援的 CLI agent」——頁面的斜線指令只開給 claude／codex，本來就這樣（列進盤點第 6 項） |
| 小助手：`aos-frontend aide-def defs/t1-aide`（抄 `templates/agent-fsm`＋蓋 `aide-def/`）→ `agent_def check` → `ctl add t1-aide-1` | 定義做得出、`problems` 空；新格式 `hookeds.json` 的 `aide_tick`（on_clock、`every_cycles: 60`）在 stack 的 `hookeds/aide_tick/` 跑起來；一分鐘內 `state/teams/t1.json` 收到 report 與 beat；`aos-frontend note` 的留話 20 秒內出現在樹上 ann 那格；小助手不佔位（`parent_by: aide`） |
| `frontend/tests`（unittest，`tests/run.sh`） | 複本 50 過、7 跳（跳的是要 aos-user 的 test_phase1 那 7 支）；改後工作樹 51 過、7 跳；給 `VIEW_TOOLS`＝舊暫存樹抄來的 aos-user：51 全過 |
| v2 網頁 `npm install`／`npm test`／`npm run build`（Node 24.14.1） | 68 過；build 過，check-dist JS gzip 104.9 KB |
| headless Chrome（`tests/cdp.mjs`）載 18768 | 看到 ann 與機房、主控台沒錯；在頁上 Ctrl+K 打 ann、打字區送「browser says 6+7」→ 頁回「已對 ann 說了」，ann 的 history 第 16 則回了 |
| 活樹 | `~/aos-home` 只讀：daemon stack 是 `~/aos-home/.stack`、`procs/` 下 `_clock _sweeper ann llm`、**沒有 `ws/` 夾**（所以沒有 `ws/tools/aos-user`）、ann 還沒有 `mailbox/`；`~/.aos/view` 只讀，沒被寫 |

今天的改動（hook 新格式、`hookeds/` 工作夾、lineage 拿掉、aos-agent 預設目標、`history -n`、`Attached` 改名、`every_ms` 拿掉）跟前端有關的兩處，`e781ef00e`、`97d4abc16` 已經順手改過前端；這次再掃 `frontend/` 全部（程式、aide-def、API.md、systemd、tests、v2 原始碼）找舊檔名、舊鍵、舊旗標、舊夾名，沒找到要改的。

## 修了哪些

| 檔 | 一句話 | 證據 |
|---|---|---|
| `frontend/bin/aos-frontend` | `do_mail`（頁上的寄信與下令都走它）寄給還沒有 `mailbox/` 的 agent 時先 `aos-post init` 建信箱，跟 `aos-mailbox send --to` 一樣；建不了就回錯、不寄 | 新測試改前紅（`MailboxMissing`）改後綠；暫存樹實寄 mail、order 都進 ann 的信箱 |
| `frontend/tests/test_delivery.py` | 加 `Mail.test_mail_makes_the_agents_mailbox`：沒信箱的 agent 寄兩封都成 | 同上 |
| `frontend/tests/test_phase1.py` | 子行程的環境多傳 `VIEW_TOOLS`（原本只拿它判斷要不要跳，跑的時候沒傳，給了也照樣去找 `~/aos-home/ws/tools`） | 改前給 `VIEW_TOOLS` 仍紅 5（`ToolMissing … /home/lorkhan/aos-home/ws/tools/aos-user/zone.py`）；改後 9 全過 |
| `frontend/API.md` | `POST /api/mail` 那段補一句「沒信箱就先建」 | — |

寄信這處**不是今天弄壞的**，之前就這樣（agent 的信箱是第一次有人用 `aos-mailbox send --to` 寄才建；測試都先建好信箱，所以沒抓到）。修它是因為今晚活樹的 ann 沒有信箱，頁上「寄信」「下令」一按就失敗（代定第 1 條）。

## 沒修的與原因

- 三個小毛病（起前端要自設 `AOS_DAEMON`、去 `~/aos-home/ws/tools` 找 aos-user、`/` 轉 `/classic` 與 v1 路徑殘留）：11-18 使用者「先留着」。其中 aos-user 那條今天變重了：活樹已經沒有 `ws/`，所以**頁上「要決定」那欄永遠是空的，回答專區信、decide 都不能用**（頁照樣起，不報錯）。
- `/compact` 等斜線指令只開給 claude／codex：agent-fsm 今天起也有 /compact，但開不開給頁面是功能設計，列盤點。
- 右欄「信箱」那格顯示的其實是 queue（排著幾則），下面「信箱裡等著的」才是 mailbox：用詞，列盤點。
- 沒動 `proto8/py`、`cpp`、範本；沒發現要動它們才修得好的。

## 給使用者的起法（今晚）

先照平常起樹（`cd ~/aos-home && source env.sh`、`aos-exec root`，那個視窗留著）。再開一個新視窗（`~/.zshrc` 已經會設 `AOS_HOME` 並 source `~/aos-home/env.sh`，`aos-frontend` 就在 PATH 上）：

```sh
cd ~/aos-home
AOS_DAEMON=~/aos-home/.stack aos-frontend serve
```

- 新版頁：<http://127.0.0.1:8768/>；舊的清單頁：<http://127.0.0.1:8767/classic>。視窗印出兩行 `aos-frontend: http://127.0.0.1:…` 就是起好了。
- 關：在那個視窗按 Ctrl-C。前端沒有留在背景跑。
- 頁上能做：看每隻 agent 與機房、點 agent 看現在／往來／做過說過、對它說話（打字區 Ctrl+Enter）、寄信、留布告欄。不能做：回答專區的信（找不到 aos-user，「要決定」那欄是空的）；對 ann 按 /compact 會被擋（頁面只對 claude／codex 開）。
- 新版頁的 build 已經放好：`~/repo/aos/proto8/frontend/ui/v2/dist/`（從 `85694d214` 的原始碼在暫存複本 build 再抄過來；`dist/` 不進 git）。原始碼改了要重來：`cd ~/repo/aos/proto8/frontend/ui/v2 && npm install && npm run build`（會多出 `node_modules/` 與一個 git 沒擋的 `package-lock.json`，不要 add）；改完要重起 `aos-frontend serve` 才會開 8768。

## 大修盤點（每項一句＋卡在哪個決定；不標推薦）

1. 把 3,100 行的 `bin/aos-frontend` 拆成幾個模組——卡在：前端還要不要維持「單檔、純標準庫」的樣子（tidy 那條「拆 aos-frontend 等大修」同一件）。
2. aos-user 改去別處找（現在寫死 `~/aos-home/ws/tools`，活樹已沒有）——卡在：專區工具 aos-user 以後放哪（收進 proto8、前端自帶、還是設定檔指）。
3. 起前端不用自設 `AOS_DAEMON`——卡在：前端是綁一棵樹（設定檔、旗標）還是照當下 shell 的樹自己找。
4. 收掉 `/` 轉 `/classic`、v1 靜態檔路徑、`API.md` 開頭仍寫 `ui/v1`——卡在：舊清單頁 classic 留不留、v2 要不要搬到第一個 port。
5. 改名（`VIEW_*` 變數、`view-api/0`、`~/.aos/view`、`[使用者經全景頁]` 等字）——卡在：前端最後叫什麼（11-15「之後會改名」）。
6. 頁上的斜線指令開給 agent-fsm（今天起它有 /compact 與 before／after_compact）——卡在：頁面對 agent-fsm 開哪些指令。
7. 新版頁不用手動 build——卡在：前端算不算 `install.py` 的一部分（收進安裝、`dist/` 回 git、或照現在手動）。
8. 小助手（aide）是一整隻假腦 agent-fsm，只為跑一個 on_clock hook——卡在：hook 換新後，要不要改成掛在隊長身上的 hook 或由前端自己算（view-1114 第 1 期的隊伍／小助手設計還要不要）。
9. 頁面每輪對每隻 agent 叫 `aos-agent ctl state`／`history ls`——卡在：前端是否只准走官方指令（`API.md` 寫的 Q7 a），還是可以直接讀 stack 的檔。
10. 右欄「信箱」那格其實是 queue——卡在：大修時 queue／信箱這兩個詞在頁上怎麼叫。
11. `~/.aos/view` 裡還有 11-14 的 `ok-*` 隊伍夾、舊 `config.json`（`say_log` 指 `wf/temp/ok-view/`）——卡在：舊的 view home 要不要清（刪檔要他說）。
12. 中轉信箱只收「寄件人名＝aide.json 寫的名字」的信——卡在：驗寄件人那四題（11-21 規劃稿）定了之後中轉信箱跟不跟。
13. systemd 範例單元——卡在：later-1115 的「systemd 規則」。
14. test_phase1 那 7 支沒有 aos-user 就跳——跟第 2 項同一個決定。

## 我代定的事

1. 寄信給沒有信箱的 agent 時先建信箱：不是今天弄壞的，但今晚活樹的 ann 沒信箱、頁上寄信下令必失敗，算「準備好」；只動實作、行為跟 `aos-mailbox send --to` 一致。要退回就還原 `do_mail` 那 5 行。
2. test_phase1 把 `VIEW_TOOLS` 傳給子行程：測試本身的不一致，不改產品找 aos-user 的方式。
3. 網頁 build 在暫存複本做、只把 `dist/` 抄進工作樹，沒在 repo 裡 `npm install`（不留 `node_modules/`、`package-lock.json`）。
4. 試跑借舊暫存樹 `~/.aos/scratch/swap-1115/r5-1115e/ws/tools/aos-user` 的抄本當 test_phase1 的替身（抄進自己的暫存夾），只為證明那 7 支在有 aos-user 時還過；proto8 裡沒有 aos-user。
5. 斜線指令對 agent-fsm 不開、右欄用詞不改：列盤點。
6. 進度檔 `overview-page` 條補一句今天的狀態（試跑過、dist 已 build、aos-user 已不在活樹）。

## 收尾

- 收掉：暫存樹 `aos-daemon-ctl shutdown`（5 隻睡下）；前端 serve、`npm install`、headless Chrome 的 pid 都已不在；18767／18768 沒人聽；`pgrep` 對過沒有留下自己的行程。別條線的行程沒動。
- 留下：`~/.aos/scratch/top-1121-frontend/`（複本、暫存樹、view home、測試與 npm 紀錄、截圖 `cdp-out3/say.png`）。
