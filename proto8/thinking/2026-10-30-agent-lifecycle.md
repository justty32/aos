# 2026-10-30 agent 的 queue、外部 coding agent 的生命週期、session 檔接管（fable 規劃）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜出發點：[10-29 agent-bob § 決定（10-30）](2026-10-29-agent-bob.md#決定10-30)（決定 33～35）｜前一份規劃：[10-29 medium-plan](2026-10-29-medium-plan.md)｜相關條文：[N-14～N-16](../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-63、N-64](../docs/NORMS/10-基礎設施-定義與工作區.md)、[P-11～P-14、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[C-65～C-67](../docs/CONCEPTS/03-基礎設施.md#資料夾程式工作區與-stack10-19)、[C-75](../docs/CONCEPTS/03-基礎設施.md#proc-之間的交流10-29)｜程式（只翻、沒改）：[lib/agent](../lib/README.md) 的 queue／history／round、[extras/human](../extras/human/README.md)、[extras/cli_hub](../extras/eca_hub/README.md)、[impls/aos-daemon](../impls/aos-daemon/README.md)、[impls/aos-post](../impls/aos-post/README.md)

規矩見 [thinking/README](README.md)。**這份整份是 fable 照原則代定的細節設計，可翻案**；使用者定的在 agent-bob 的決定 33～35。條文草稿標「草稿、待使用者看」，**NORMS／CONVENTION 正文沒動、程式沒動**。衝突與方向題寫在文末，寫給不看 CS 術語的人。**10-30 使用者「都照建議」→ [§ 決定（10-30）](#決定10-30)**。**10-30 第 10 步落正文（縮小範圍）**：只落跟第 1～5、7、8 步直接相關的條文，hub 那部分暫緩；每條的狀態標在[條文草稿](#條文草稿草稿待使用者看不改-normsconvention-正文)各條上。

## 前提（引用哪些決定）

- **決定 33**（agent-bob）：say 改走標準的有順序投遞、題目信箱退場；**agent 這一層不用「信箱」這個詞，這層是訊息的 queue**；請求的投遞叫信箱或 queue 都可以。
- **決定 34**：**aos-loop 是 aos agent 這支程式的內部組件**（停著等由它提供，agent 保持是函數）；其他 coding agent 是黑盒子，生命週期在外面包、含掛到 aos-daemon 底下；daemon 管不了純 aos-exec 就擴充；沒有也行，`ps aux`＋`kill`。
  - 使用者 10-30 早補（逐字）：「**包成max:1也是可以**」——純 `aos-exec X` 用現有 loop 規格包成 `max: 1` 掛 daemon，他接受。
  - 再補（逐字）：「**不過可以的話，我也覺得讓daemon可以掛aos-exec，也是不錯的**」——daemon 原生就能掛一個純 `aos-exec X` 的子項更好。所以 B 題兩條都規劃，② 原生為建議方向、① `max: 1` 為現況與底層。
- **決定 35**：對話簿放 stack、hub 的 pause 改名「收起」、規則寫進 CONVENTION 引用 N-16／N-14；**claude code cli 這類自己存 session 的，aos 要弄一份 symlink 或複製一份過來管理**。
- 承接的：[10-28 medium](2026-10-28-medium.md) 決定 1（納入管理透過介質、直接 aos-exec＝Linux 管）、2（aos-loop＝常駐＋狀態＋手把的包裝）、22（身分＝路徑）、25（人算 proc、`~/`）、26（紀錄 aos 不管、不進交流標準）、27（失敗不另外通知）、28（三種基本概念：投遞、窗、父子交代）、32（agent 的輸入是 queue）；[10-28 hub-kernel](2026-10-28-hub-kernel.md) 決定 5（pause／stop）、9（hub 是 kernel 的一種）、11（prompt＝stdin／stdout 當 queue）、13（插話等或打斷不訂死）；[10-28 hub-adapter](2026-10-28-hub-adapter.md) 使用者「放Stack比較好。」；[10-29 playground-queue](2026-10-29-playground-queue.md) 結論 2（跑完結不結束寫死在定義裡）。
- 實作現況（這次翻過的，細節在各題裡）：aos-daemon 的子項**一律**包成子 aos-loop（`child.cpp` `spawn`：字串子項包成 `{"exec": 它}`、蓋 `_entry: aos-loop`、寫小格 `loop.json`、fork 後 `run_cli`）；aos-loop 的 `paused`／`stopped` 只在兩次之間生效、跑的期間不讀 ctl；aos-say 放 `<工作區>/new/`（沒設 `AOS_STACK` 且 `.stack/new/` 在就改用 `.stack/`）、aos-listen 等 `out/<題名>`、偷看讀 stack 的 `history.jsonl`／`trace.jsonl`；lib 的 `queue` 格就是 P-11 四格的操作器（`claim` 把題文經 history 格接成 user）；round 看「`cur/` 有沒有題、history 最後一則是誰」決定下一步、沒題退 10；aos-hub-kernel 替實例收 `<資料夾>/.stack/new/` 的題、stop 時用 glob `~/.claude/projects/*/<id>.jsonl`（codex `~/.codex/sessions/**/*<id>.jsonl`）拷對話檔；aos-post 有 `init／send [--ordered]／claim／claim-all／check／finish [--keep] [--reply]／withdraw`。

## 各題結論（每條標照哪條原則／決定）

### A. agent 層的 queue

1. **queue＝有順序投遞（N-16）在 agent 層的名字**；它不是新機制，是 N-16 有序信箱的一個實例，只是這一層叫它 queue、裡面一封信叫「一則訊息」。（決定 33「這一層是訊息的 queue」；C-54 一詞一義：queue＝一場對話的輸入、順序是意思的一部分；信箱＝獨立的請求。）
2. **位置：`$AOS_STACK/queue/`**，不在工作區。佈局照 N-16 有序信箱：`queue/tmp/`、`queue/new/`、`queue/cur/`、`queue/order.lock/`、`queue/order.json`；`done/` 選用（agent 想留才有，預設處理完就刪）。理由：對話是**這次執行的狀態**，不是交給上層的成果（決定 35 把 history 放 stack 的同一個理由）；aos-say／listen 要摸的東西（queue、history、ctl／state）因此**全在一個 stack 裡**，hub 的「信箱放 `.stack/`」（使用者 10-28）跟 aos agent 變成同一條規則，say／listen 現在那條「`.stack/new/` 在就改用 `.stack/`」的特例可以拿掉；工作區只剩使用者的檔與成品（C-65 的本意、使用者 10-16「我不喜歡 /ws 底下出現一個 work/」）。跟 C-65 原文字面的出入列在[衝突 1](#衝突跟既有原則實作對不上的寫給使用者看)。
3. **一則訊息＝一封 N-16 的信**，`letter.json` 照信封（`kind: "letter"`、`sender`、`sent_at`、選填 `reply_to`／`in_reply_to`），**`body`＝一則 OpenAI message 物件**（`{"role": "user", "content": "…"}`，有需要也可以是 `system` 或帶 `name`），agent 收到就把 `body` 原樣接進 `history.jsonl`——queue 的一則＝history 的一行，兩邊同一個形狀，不用轉換（P-41 history 一行一則 OpenAI message；C-56 不多造格式）。不是物件、沒有 `role`＝壞信，照 N-16 丟掉、記 `letter_warning`（agent 有 state 窗才記；aos-loop 開了窗就有）。
4. **queue 只收有序的信**（N-16「一個有序信箱只收有序的信」）：寄＝`aos-post send --ordered $AOS_STACK/queue`；非有序的信進來＝壞信。
5. **誰認領、怎麼算「處理完」**（照現行 round 與 queue 格的順序，只換資料夾）：`claim`＝`aos-post claim`（rename 進 `cur/`）＋把 `body` 經 history 格 `append`；**信留在 `cur/` 直到這題答完**；`finish`＝assistant 那則已在 history 之後才 `aos-post finish`（預設刪、`--keep` 進 `done/`）。所以「信還在 `new/` 或 `cur/`」＝還沒答，「信不見了」＝答案已在 history。失敗（P-20）＝信留 `cur/`、人修好重跑接著做，照舊。插話（act 決定打斷、`claim --more`）照舊：`cur/` 裡幾封就幾封一起算答完。
6. **回答怎麼回：不另開回答通道，答案就是 history 最新那則 assistant**（決定 11 prompt＝stdin／stdout 當 queue、決定 26 紀錄是各程式自己的檔、C-56）。`out/` 退場後不需要 `reply`：queue 是一場對話，不是一問一答；想要一問一答（agent 問 agent、ask_round）的人用 N-16 的 `reply_to` 自己做，標準不保證一題配一答（N-16 原本就這樣寫）。
7. **aos-say 改成**：`aos-say [--ws WS] [--stack STACK] [話...]`＝`aos-post send --ordered <stack>/queue`，stdout 印信號；stack＝`--stack` ＞ `$AOS_STACK` ＞ `<WS>/.stack/`（N-57 預設值）。沒有 `queue/` 就建（`aos-post init`）——寄信人建信箱是為了「可以先說再跑 agent」（10-24 決定 6 的精神）；不再寫工作區頂層的 `.say-*.tmp`、不再有 `--name`（信號由 aos-post 給；要對應就拿信號）。
8. **aos-listen 改成只看 stack**（N-14 窗、N-13 stack 裡的檔）：
   - `aos-listen <信號>`：信還在 `queue/new/` 或 `queue/cur/` 就等；不見了就印 history 最新那則沒有 `tool_calls` 的 assistant 的 `content`；四處都沒這封、history 也沒新 assistant＝`QuestionUnknown`；服務者 trace 說失敗就照舊講出來。
   - `--follow`／`--last N`：直接跟 history（只印 assistant，`--trace` 連 tool 一起）。
   - `--status`：誰在服務（`/proc` 掃 `AOS_WS`／`AOS_STACK`、或 stack 的 `server.txt`）、**aos-loop 的 `state.json` 的 `phase`**（看得出 `paused`，補上 agent-bob 實跑時「狀態一欄是 `-`」的缺口）、queue 四格各幾封、history 幾則。
9. **P-11 題目信箱退場，各處要改什麼**（實作步驟有逐項）：lib `queue` 格的 push／pop／claim／finish／peek／current／done／withdraw 全改到 `$AOS_STACK/queue/`（底下叫 aos-post，不自己再寫一套 rename；push＝`send --ordered`、withdraw＝`aos-post withdraw`、pop＝照上面 listen 的規則等）；round 的 `where` 看 queue 的 `cur/`／`new/`；`ask_round` 改 push 再照 listen 規則等；aos-hub-kernel 改收 `<資料夾>/.stack/queue/`、答案接進 `<資料夾>/.stack/history.jsonl`（一則 user、一則 assistant）；aos-say／listen／chat 與 `lib/aos/aos_ws.py` 照 7、8；試驗場 agent-bob-1／bob-2 照新協議。**舊的 fsm 範本（agent-bob／ann／dan、topdown）不改**，P-11 留給它們、標「舊協議」（P-11 的 10-29 加註本來就說「照舊用，新東西才走標準」）；代價是 say／listen 不再認它們，見[方向題 1](#方向題原則推不出的附背景例子)。
10. **「agent 之間的請求投遞」叫信箱**，不叫 queue（使用者說都可以，這裡定一個）：請求是一封封獨立的信（可能要回信 `reply_to`、可以不照順序、處理者可能好幾個），跟對話的性質相反；一個詞一個意思（C-54），queue 專指對話那條。資料夾名慣例 `inbox/`（playground 已用），位置照 N-16 由擁有者定、別人靠 hub 型變數或明給找到（N-63）。要不要讓 agent 自己去看信箱，照決定 32 以後放 tools，這份不碰。

### B. 納管外部 coding agent 的生命週期

11. **aos agent：agent 是函數、停著等交給 aos-loop**（決定 34；N-53）。範本 `_entry` 寫 `["aos-loop", "loop.json"]`，`loop.json` 開窗 `"ctl": "ctl.json"`、`"state": "state.json"`（落在 `$AOS_STACK`）。暫停／停＝寫 `$AOS_STACK/ctl.json` 的 `paused`／`stopped`（N-07），一次＝一輪 round；agent-bob-2 那種自己寫循環、自己讀 ctl 的做法**不做**（agent 這層照舊沒有 ctl，NORMS 窗那份開頭的話不用改）。
    - **跑完要不要結束寫在定義裡**（playground-queue 結論 2），落在 round 這格的一個設定：`ROUND_ON_EMPTY=stop`（預設；queue 空＝退 10、loop 收工＝**射後不理**）或 `idle`（queue 空＝退 0、什麼都不做，由 loop 的 `interval_ms` 隔一下再來＝**射後有理**，停著等）。寫在 `parts.json` 那格的 `env` 或 round 格的 `.env`（P-25 的 10-28 加註）。不加阻塞等待的程式（KISS）；pause／stop 的反應時間＝`interval_ms`。
    - 場景二「暫停狀態機、改東西」＝fsm agent 的 loop `paused` 停在格與格之間，本來就有；round agent 的 `paused` 停在輪與輪之間（一次比較大）。同一個詞同一個意思（N-07），「一次」多大各程式自己說（agent-bob 衝突 3 的建議，使用者決定 35 照隊長）。
12. **外部 coding agent（黑盒子）掛 aos-daemon**，兩條：
    - **① 現況就能用：包成 `max: 1` 的 loop**（使用者「包成max:1也是可以」）。daemon.json：`"loops": {"bob": {"exec": "/path/agent-bob", "max": 1}}`（相對路徑從 daemon 的 cwd 算，N-28）。生命週期：daemon 起子 aos-loop（小格 `$AOS_STACK/bob/`，`AOS_STACK`＝小格）→ loop 跑一次 `aos-exec /path/agent-bob` → 退 0 或 10＝loop 以 0 結束、`loops_state.json` 那列 `done`，不自動重起（N-28 10-20 落實 ②）；退非 0＝loop 以那個碼結束、列上記 `code`。**沒寫 `max`＝退 0 就立刻再跑一次**（`interval_ms` 預設 200），一次性的東西一定要寫 `max: 1`。停：`loops_removed` 或 daemon 收工 → daemon `kill(loop pid, SIGTERM)` → loop 轉 `kill(子 pid, SIGTERM)`（aos-exec 已 exec 成入口，所以就是那支程式）→ 它自己收 → loop 以 128＋15 結束；10 秒不退＝daemon SIGKILL 整個 session 群組（P-36）。**代價**：多一層 aos-loop 行程；外層 loop 的 `ctl.json`／`state.json` 寫在小格，**跟掛進去的 aos agent 自己的 loop 窗撞同一個檔**（agent 的 `loop.json` 也開 `state.json`、兩個 loop 寫同一份 state＝N-28 開頭 ② 警告的狀況），要掛 aos agent 得把裡面那層的窗改名（`agent_state.json`）或不開窗；純黑盒子（`claude -p` 的腳本）沒這問題。
    - **② 建議方向：daemon 原生掛一個 exec 型子項**（使用者「讓daemon可以掛aos-exec，也是不錯的」）。daemon.json 多一個選填 key **`execs`**，形狀同 `loops`：`{"名字": 目標}` 或 `{"名字": {"exec": 目標}}`，目標＝aos-exec 的目標（字串或 `[目標, 參數...]`，同 N-28）。daemon 直接 `aos-exec` 它一次：小格照舊 `$AOS_STACK/<名字>/`、`AOS_STACK`＝小格、stderr 附加到小格的 `stderr.txt`、自成 session 群組、stdin 接 `/dev/null`——跟起子 loop 一模一樣，**只是中間不包 aos-loop、不寫小格的 `loop.json`、不補 `ctl`／`state`**。它退了＝那列 `done`（記 `code`／`signal`），不重起；要再跑就從名單拿掉再放回（同 loop 型）。state：`loops_state.json` 多一張 **`execs` 表**，每列同 `loops`（`pid`、`started_at_ticks`、`phase`、`code`、`signal`），`phase` 同一套（N-17）；`adopt` 兩張表都接。管轄手把：`loops_ctl.json` 與信箱模式的信多認 `execs_added`／`execs_removed`，語意同 `loops_added`／`loops_removed`（N-54）。停：SIGTERM **直接打那支程式**、10 秒 SIGKILL 整群，少一跳。撞名：`execs` 與 `loops` 共用一個名字空間（小格同一個資料夾）。**為什麼比 ① 好**：少一層行程、小格裡沒有外層的窗跟 agent 自己的窗打架、daemon 的表直接說「這是一次性的」；aos-loop 包著一次性的東西本來就只是為了「有個子項可以管」，拿掉是 C-56 最後一步的減法。要動 N-28「daemon 多的只有 `loops`、`adopt`」與 N-54，列在[衝突 3](#衝突跟既有原則實作對不上的寫給使用者看)。
    - **沒掛 daemon＝Linux 管**（決定 1；使用者「linux本身的proc管理就夠」）：寫成一句條文，aos 不另做 `aos-ps`。
13. **aos-hub 留什麼、什麼併進 daemon**：hub 是替**要畫面、要接回舊對話**的外部 CLI 做的（tmux、Ctrl-]、`--resume`、session 檔），這幾樣 daemon 做不到（daemon 的子項沒有終端機），**全部留在 hub**；hub 的 `pause` 改名 **`close`**（跟 `open` 成對：關畫面、對話留著、照樣收題），`stop` 照舊；hub 的「收題」改走 queue（A-9）；hub 的 `ls`／`state`（誰被納管）對 daemon 那邊的對應物就是讀 `loops_state.json`，不另做指令。hub-kernel 本身要不要掛在 daemon 底下當一個 `execs` 子項：可以、不強制（hub-kernel 決定 14「沒差」）。「暫停＝不收新題」留給 N-07 的 `paused`，hub 沒有這個動作、也不加（要「先別動」就別 say）。

### C. 外部 agent 的 session 檔接管

14. **實際佈局**（WSL 看過目錄名、沒讀內容）：claude code 在 `~/.claude/projects/<cwd 編碼>/<session-id>.jsonl`，資料夾名是把 cwd 的 `/`（跟 `_`、`.` 這類非字母數字）換成 `-`（例 `-home-guanyu-code-try-hub-say-proj`；Windows 這邊 `C:\code\mine\simple_tools\aos` 變 `C--code-mine-simple-tools-aos`，底線也被換掉）——**編碼是有損的、不能從資料夾名反推 cwd，也不該由 aos 自己算**；session id 可以由我們給（`--session-id <uuid>`，hub 已經這樣做），所以檔名是知道的，找檔用 `projects/*/<id>.jsonl`（cli_session 現在就是這樣）。`CLAUDE_CONFIG_DIR` 會把整個設定（含登入）搬走，不能拿來只搬 session。codex 在 `~/.codex/sessions/<年>/<月>/<日>/rollout-<時間>-<thread-id>.jsonl`（另有 `archived_sessions/`、`session_index.jsonl`），id 從 `thread.started` 拿，`CODEX_HOME` 同樣是整個搬。pi 這台沒裝。
15. **放哪**：實例的小格 **`<資料夾>/.stack/<工具名>/transcripts/<kind>-<id>.jsonl`**（C-65 執行中的東西落 stack；hub 現在歸檔時已經有 `hub_archive/<工具名>-<UTC>/transcripts/`，只是提早到一開始就有）。
16. **symlink 還是複製：活著時 symlink、結束時換成複製**。CLI 一邊講一邊寫同一個檔，symlink 永遠是最新的、零成本；`aos-hub stop` 歸檔時把 symlink 換成真的複製（現行 stop 的拷貝照舊），因為 claude code 會自己清舊 session（預設 30 天），複製才留得住。活著時發現 symlink 指不到（CLI 自己清了、或 `--no-session-persistence`）＝`listen --status`／`aos-hub state` 說一句「CLI 自己的對話檔已不在」，不報錯、不補（決定 27 的精神：不保證）。
17. **何時建、誰建**：**hub-adapter（`lib/agent/cli_session.py`）**在拿到 session id 那一刻建（claude：非互動第一次跑或開畫面時；codex：收到 `thread.started`）——它是唯一知道 id 的人；`register` 進 hub 的「只登記」實例也建（它們也經 cli_session 起）。刪：`aos-hub stop` 把小格搬去 `hub_archive/` 時 symlink 一起搬、換成複製；小格被人 `rm` 就一起沒了（P-17 叫完不自動收、要收由呼叫方 `rm`）。
18. **跟決定 26「紀錄 aos 不管」**：26 說的是**交流標準**不管紀錄（trace／history 是各程式自己的檔），這裡是 hub 這支程式替黑盒子留一個指向它自己紀錄的連結，不進 NORMS、只寫在 hub 的說明與 CONVENTION 的 adapter 那條；字面上的出入列在[衝突 2](#衝突跟既有原則實作對不上的寫給使用者看)。

### D. 其餘三題照隊長建議（決定 35）

19. **history 放 `$AOS_STACK/history.jsonl`**（P-41 原樣）：playground-queue 代定 3、agent-bob 代定 10 翻案，試驗場 bob-1／bob-2 改回 stack。aos-listen 的偷看因此直接看得到。
20. **hub 的 pause 改名 `close`**（「收起」；跟 `open` 成對），`aos-hub close [--idle 分]`，`reap.json` 跟著改；`paused` 這個字只留給 N-07「不起新的一次」。
21. **規則寫進 CONVENTION 的 agent 對話協議**：P-11 改口成「queue」那條、新一條 P-42 把 queue（引 N-16）、history（引 N-14／N-13）、ctl／state（引 N-07、aos-loop）、`server.txt`（選用）四樣點名，aos-say／listen／hub 都照它；條文草稿在下一節。

## 條文草稿（草稿、待使用者看；不改 NORMS／CONVENTION 正文）

> 10-30 使用者「都照建議」後落了一部分（第 10 步，範圍縮小：第 6 步 aos-hub 與第 9 步試驗場使用者 10-30 先暫停）；每條標「已落正文（10-30）」或「暫緩」。正文才是準的，下面保留草稿原文。

### CONVENTION 四、題目與答案

- **已落正文（10-30）**：[CONVENTION/02](../docs/CONVENTION/02-題目stack停錯腦.md) P-11 的 10-30 改口。**P-11 改口（10-30）**：「題目＝`$AOS_WS/new/<題名>`……答案＝`$AOS_WS/out/<題名>`」整段改讀成：**aos agent 的輸入是 queue**——`$AOS_STACK/queue/`，一個 [N-16](../docs/NORMS/05-基礎設施-窗.md) 的**有順序信箱**，一封信＝一則訊息（`body` 是一則 OpenAI message，照 P-41 history 的一行）；agent 認領（rename 進 `cur/`）就把 `body` 接進 `history.jsonl`，答完（assistant 那則已進 history）才把信收掉（預設刪、要留紀錄進 `done/`）。**回答就是 history 最新那則 assistant，沒有別的回答通道**；檔案成品照舊落在工作區（「結果＝工作區內容」那句只管檔案）。原本的 `new/`、`cur/`、`out/`、`done/` 四格留給 10-30 前的 fsm 範本（agent-bob／ann／dan、topdown），標**舊協議**，新東西不用；aos-say／listen 不再認它。（決定 33、35；N-16；C-65 執行中的東西落 stack；C-56）
- **已落正文（10-30）**：P-12～P-14 各一條「10-30 跟著改口」。**P-12、P-13、P-14 跟著改口**：P-12「一次做一題、`cur/` 有沒做完的先接」照舊，資料夾換成 queue 的；P-13 附檔＝信資料夾裡的其他檔（N-16「其他檔隨意」），`prompt.txt`／`answer.txt` 不再需要；P-14「agent 只動 `new/`…與 `$AOS_STACK`」改成「agent 只動 `$AOS_STACK` 與工作區裡它說明寫明的檔」。
- **已落正文（10-30），只落 ①～③ 與「跑完要不要結束」**：[CONVENTION/02](../docs/CONVENTION/02-題目stack停錯腦.md) 的 P-42（第四節，P-14 之後；寫「人經 aos-say／aos-listen 碰這三樣」）。④ `server.txt` 與「aos-say／aos-listen／aos-hub 都照這四樣，不管後面是 aos agent 還是外部 CLI」**暫緩（10-30）**：hub／外部 agent 那部分等使用者定 aos-eca-hub（實作第 6 步暫停，[10-30 map-review](2026-10-30-map-review.md#決定10-30) 第 5 點）。**新 P-42 agent 對話協議（10-30）**：人或程式要對一隻跑著的 agent 說話、看它說什麼、停它，只碰它的 stack 四樣東西：① **queue**＝`$AOS_STACK/queue/`（N-16 有順序投遞；寄＝`aos-post send --ordered`）；② **history**＝`$AOS_STACK/history.jsonl`（只附加；偷看就是讀它，N-13 外顯的檔）；③ **ctl／state**＝aos-loop 開在 `$AOS_STACK/ctl.json`、`state.json` 的窗（N-07 `paused`／`stopped`、N-17 `phase`）——停著等的能力由 aos-loop 提供，agent 本身仍是函數、沒有 ctl；④ **`server.txt`**（選用）＝不是 aos-loop 在服務時（例 aos-hub-kernel 代答）寫一行「`<pid> <程式名>`」讓人知道誰在服務。aos-say／aos-listen／aos-hub 都照這四樣，不管後面是 aos agent 還是外部 CLI。**跑完要不要結束寫在定義裡**：round 格的 `ROUND_ON_EMPTY=stop`（queue 空退 10、loop 收工）或 `idle`（退 0、由 loop 的 `interval_ms` 再來）。（決定 11、33～35；N-14、N-16、N-07、N-53；C-75）

### NORMS 窗 N-16 加註

- **已落正文（10-30）**：[NORMS/05](../docs/NORMS/05-基礎設施-窗.md) N-16 的 10-30 加註。**10-30 加註：queue**：agent 層把自己的輸入叫 **queue**，它就是本條的有順序投遞、資料夾叫 `queue/`、位置在那隻 agent 的 `$AOS_STACK`（CONVENTION P-42）；「信箱」這個詞留給 agent 之間的請求投遞。本條內容不變。

### NORMS loop 與 daemon N-28、N-54 加註（exec 型子項，②）

- **已落正文（10-30），照實作寫**（def6f2a3）：[NORMS/04](../docs/NORMS/04-基礎設施-loop與daemon.md) N-28 的「10-30 補：exec 型子項 `execs`」；比草稿多寫實作有的幾件（單子物件不收＝`CfgBad`、stdout 也接 `/dev/null`、cwd＝daemon 的 cwd、換種類＝收舊起新、分頁同 `loops_state_loops/`），並指到 [aos-daemon-ctl](../bin/README.md)（工具、不算規範；`AOS_DAEMON` 寫成 N-63 的 10-30 補）。**N-28 10-30 補：`execs`**：daemon.json 多一個選填 key `execs`＝一次性的子項，形狀同 `loops`（`{名字: 目標}` 或 `{名字: {"exec": 目標}}`；目標＝aos-exec 的目標、相對路徑從 daemon 的 cwd 算）；daemon 對每項直接 `aos-exec` 一次（小格 `$AOS_STACK/<名字>/`、`AOS_STACK`＝小格、stderr 附加到小格 `stderr.txt`、自成群組、stdin `/dev/null`），**不包 aos-loop、不寫 `loop.json`、不補 `ctl`／`state`**；退了＝`done`、記 `code`／`signal`、不重起。`loops_state.json` 多一張 `execs` 表，列的形狀與 `phase` 同 `loops`；`adopt` 兩張表都接。收法同子 loop（SIGTERM 直接打它、10 秒 SIGKILL 整群）。`execs` 與 `loops` 共用名字空間。「daemon 多的只有 `loops`、`adopt`」改成「多的只有 `loops`、`execs`、`adopt`」。要一次跑完的東西也可以照舊寫成 `{"exec": 它, "max": 1}` 的 loop（使用者 10-30「包成max:1也是可以」），差別只在多一層 aos-loop 與它的窗。
- **已落正文（10-30），照實作寫**：N-54 的「10-30 補：`execs_added`／`execs_removed`」，多寫 loops_ctl 沒有整份的 `execs`、同名的處理。**N-54 10-30 補**：`loops_ctl.json` 與信箱模式的信多認 `execs_added`／`execs_removed`，語意同 `loops_added`／`loops_removed`。
- **已落正文（10-30）**：放成 N-28 底下的「10-30 補：沒掛 daemon＝Linux 管」（開頭那段「不管」是 10-22 使用者列的自行承擔清單，不往裡加）。**一句（放 N-28 開頭那段「不管」之後）**：直接 `aos-exec` 跑的東西歸 Linux 管（`ps`、`kill`），aos 不另做程式；要納進 aos 就掛 daemon（[10-28 medium](2026-10-28-medium.md) 決定 1、使用者 10-30）。

### CONCEPTS C-65 例子改口

- **已落正文（10-30）**：[CONCEPTS/03](../docs/CONCEPTS/03-基礎設施.md) C-65 的「10-30 改口：括號裡的例子」（原文保留、加改口）。「工作區只放交辦的東西與成果（`new/`、`cur/`、`done/`、`out/` 這類，P-11、P-14…）」→ 括號裡的例子改成「使用者的檔、agent 寫出的成品檔」；對話（queue、history）是這次執行的狀態、落在 stack（P-41、P-42）。本條其餘不動。

### hub 的說明（extras/cli_hub、CONVENTION adapter 那段）

**暫緩（10-30）**：這一節整節等使用者定 aos-eca-hub（實作第 6 步暫停，[10-30 map-review](2026-10-30-map-review.md#決定10-30) 第 5 點）。

- `pause` → `close`（關畫面、對話留著、照樣收題）；`stop` 照舊。
- 代答實例的收題改走 `<資料夾>/.stack/queue/`，答案接進 `<資料夾>/.stack/history.jsonl`。
- **session 檔接管**：拿到 CLI 的 session id 就在小格建 `transcripts/<kind>-<id>.jsonl` → 指到 CLI 自己的檔（claude `~/.claude/projects/*/<id>.jsonl`、codex `~/.codex/sessions/**/*<id>.jsonl`）的 symlink；`stop` 歸檔時換成複製；指不到就說一句、不補。（決定 35；C-65；不進 NORMS）

## 實作步驟（分步、每步可驗；都在 proto8，Linux／WSL 跑測試）

| 步 | 做什麼 | 動哪些檔 | 怎麼驗 |
|---|---|---|---|
| 1 | **lib `queue` 格改到 `$AOS_STACK/queue/`**，底下叫 aos-post：`push`＝`init`（沒有才建）＋`send --ordered`、印信號；`claim [--more]`＝`aos-post claim` ＋ 把 `body` 經 history 格 `append`（最後一則已是 user／tool 的規則照舊）、`current.txt` 寫信號；`finish [--keep]`＝`cur/` 全部 `aos-post finish`；`pop <信號>`＝照 A-8 等；`peek／current／done`＝列 `new/`、`cur/`、`done/`；`withdraw`＝`aos-post withdraw`；`emit` 不變 | `lib/agent/queue/_entry`（PATH 要有 aos-post）；壞信記 `letter_warning` 這件交給 round（它才知道有沒有 state 窗）先不做 | `tests/test_round_queue.py` 全部改成 queue 佈局（push 之後 `queue/new/` 有一封、claim 之後 history 多一則且信在 `cur/`、finish 之後信不見、`--keep` 進 `done/`、非有序的信＝壞信）；**做了（58c278f4）** |
| 2 | **round**：`where` 改看 queue 的 `cur/`／`new/`；加 `ROUND_ON_EMPTY`（`stop`＝退 10、`idle`＝退 0 不做事） | `lib/agent/round/_entry` | `tests/test_round.py`：現有各案改佈局；新案「`ROUND_ON_EMPTY=idle` 時 queue 空退 0、history 不動」「在 aos-loop 下 `idle`＋`interval_ms` 跑著，寫 `ctl.json {"paused": true}` 後 say 的信留在 `new/`、放行後答出」；**做了（12a17a21）**；另改 act 的插話看 queue 的 `new/` |
| 3 | **範本 agent-nia 與 demo**：`loop.json` 開窗（`ctl`、`state`）、`parts.json` round 的 env 給 `ROUND_ON_EMPTY`（範本預設 `stop`）；README 寫兩種定義怎麼寫 | `demo/agent-nia/*`、`demo/README.md` | `tests/test_nia.py` 改用 aos-say／aos-post 放題、看 history；**做了（e6496397）** |
| 4 | **aos-say／listen／chat**：say＝`aos-post send --ordered <stack>/queue`（收 `--stack`、拿掉 `--name` 與 `.say-*.tmp`、拿掉「`.stack/new/` 在就改用」那條）；listen 照 A-8（等信號、`--follow`／`--last` 看 history、`--status` 加 loop 的 `phase`）；chat 跟著；`aos_ws.py` 的 put／wait 改 | `extras/human/bin/*`、`lib/aos/aos_ws.py`、`extras/human/README.md` | `tests/test_human.py`：假 agent 改成「aos-post claim → 寫 history → finish」；新案「答案先到再 listen 不漏」「信還在 cur/ 時 listen 等」「`--status` 看得到 `paused`」；**做了（121ee96c）**；aos-ai、ask_agent／spawn_agent、nvim 外掛跟著改（實作時代定 Q-11、Q-16） |
| 5 | **ask_round**：push 後照 listen 規則等（信不見＋history 新 assistant） | `lib/aos/ask_round/_entry` | `tests/test_nia.py` 那段、`tests/test_lib.py`；**做了（b2c562c4）** |
| 6 | **aos-hub**：kernel 收 `<資料夾>/.stack/queue/`（`add` 時 `aos-post init`）、user／assistant 各接一行進 `.stack/history.jsonl`；`pause` → `close`（`reap.json`、README、`aos-hub` 說明）；cli_session 拿到 id 就建 `transcripts/<kind>-<id>.jsonl` symlink、`stop` 換成複製、指不到就在 `state`／`ls` 說一句 | `extras/cli_hub/bin/aos-hub-kernel`、`bin/aos-hub`、`reap.json`、`lib/agent/cli_session.py`、README | `tests/test_hub.py`：say／listen 經 queue；新案「add 後小格有 symlink、stop 後 `hub_archive/.../transcripts/` 是真檔」「symlink 目標刪掉後 state 說一句、退 0」；**暫停（10-30 使用者：aos-hub 要先摘出通用部分、改名 aos-eca-hub）**；工人做完的成品凍結在分支 `wip/hub-step6`（42f1be73），沒進 main；main 上 test_hub 經 say／listen 四案先 skip |
| 7 | **aos-daemon `execs`（②）**：`daemon.cpp` 讀 `execs`（形狀同 `loops`、同一套 `check_lists`、撞名共用）；`child.cpp` 多一種 spawn（不寫 `loop.json`、`run_cli({"--", 目標, 參數...})`）；`loops_state.json` 多 `execs` 表、`adopt` 接；`loops_ctl.json`／信箱多認 `execs_added`／`execs_removed`；`term`／`settle` 共用 | `impls/aos-daemon/src/daemon/{daemon,windows,mailbox}.cpp`、`src/child/child.cpp`、README、code map `proto8/14-aos-daemon.md` | `tests/test_daemon*.py`：新案「`execs` 一項跑完＝`done`、記 `code`、不重起」「`execs_removed` 送 SIGTERM、不理的 10 秒 SIGKILL 整群」「`execs` 與 `loops` 撞名＝CfgBad」「adopt 接回 `execs` 列」「`{"exec": X, "max": 1}` 的 loop 型照舊能跑（①）」；**做了（def6f2a3）**；另加命令列 `aos-daemon-ctl`（使用者 10-30 加的，代定 D-8～D-16） |
| 8 | **demo/daemon-3**：一份 daemon.json 同時掛一個 loop 型與一個 `execs` 型（例 `execs: {"bob": "/path/agent-bob-1"}`）；README 寫 ① 跟 ② 兩種寫法 | `demo/daemon-3/*`、`demo/README.md` | 跑一次、看 `loops_state.json` 兩張表；**做了（c0605f63）**；run.sh 的 daemon-3 段跟第 3 步一起進 |
| 9 | **試驗場 `~/code/playground`**（不進 git）：bob-1 不變（history 改回 stack）；bob-2 改成「函數＋aos-loop」：`_entry: ["aos-loop", "loop.json"]`、loop.json 開窗、`interval_ms` 300、本體每次 `aos-post claim` 一封 → `claude -p` → history → `finish`、沒信退 0；再用 ① 與 ② 各掛一次到 daemon 底下；最後拿一隻 fsm agent（agent-dan 加 ctl 窗的 loop）試場景二「paused 停在格之間改東西」 | 試驗場 README | say／listen 一行沒改就能用；`listen --status` 看得到 `paused`；daemon `loops_removed`／`execs_removed` 能收掉；**暫停（10-30 使用者：「腦用 claude -p」有保留，射後有理與 queue 要分 aos agent 與外部 agent 兩塊各自看）** |
| 10 | **條文落正文**（等使用者看過這份）：P-11～P-14 改口、新 P-42、N-16 加註、N-28／N-54 補、C-65 例子改口、hub 說明；條號表、各批出處、code map、thinking 同步。**10-30 做了縮小範圍的那部分（18cc5662）**（跟 1～5、7、8 步直接相關的；hub 說明與 P-42 的 hub／外部 agent 部分暫緩，見條文草稿各條的標記） | docs、wf | `wf-lint` broken=0 |

順序：1→2→3→4→5 是 queue 那條線（每步 WSL 跑 proto8 全套）；6 獨立；7→8 獨立；9 在 1～7 之後；10 最後。

## 衝突（跟既有原則、實作對不上的；寫給使用者看）

1. **對話的輸入放 stack，跟 C-65 原文的例子字面不合。** C-65 寫「工作區只放交辦的東西與成果（`new/`、`cur/`、`done/`、`out/` 這類）」，P-11 也把題目放在工作區；這份把 queue 放進 `$AOS_STACK/queue/`。**各選項後果**：放工作區（`$AOS_WS/queue/`）＝使用者的專案資料夾會長出一個 `queue/`（你 10-16 說過不喜歡 ws 底下出現 `work/`），hub 那種「資料夾＝你的程式專案」的情況你 10-28 已經選了放 `.stack/`，兩種 agent 就變兩條規則；放 stack＝工作區乾淨、aos agent 跟 hub 同一條規則、say／listen 只要找 stack，但 C-65 括號裡的例子要改口（對話是執行狀態、不是成果）。**建議**：放 stack，C-65 例子改口（草稿在上面）。 **已定：照建議（使用者 10-30「都照建議」）。**
2. **替黑盒子留 session 檔，跟決定 26「紀錄 aos 不管」字面上相反。** 26 說交流標準不管「發生過什麼」；決定 35 又要 aos 弄一份 symlink 或複製。**後果**：寫進 NORMS＝26 要改口；只寫在 hub 的說明＝標準照舊、這是 hub（adapter）自己的功能。**建議**：不進 NORMS，寫在 hub 說明與 CONVENTION 的 adapter 段；26 不動。 **已定：照建議（使用者 10-30「都照建議」）。**
3. **daemon 原生掛 exec 型子項（②）要動 N-28、N-54。** N-28 寫「daemon 多的只有 `loops`、`adopt`」、子項一律是子 loop；N-54 的手把只認 `loops*`。**後果**：只用 ①＝條文不動，但掛一隻 aos agent 時外層 loop 的窗跟它自己的窗撞同一個檔（要改名或不開窗），而且每個一次性的東西都多一層行程；做 ②＝N-28 多一個 key、state 多一張表、手把多兩個 key，程式約一天。**建議**：做 ②，① 留著當底層與過渡；條文草稿在上面。 **已定：照建議（使用者 10-30「都照建議」）。**
4. **say／listen 不再認舊的 `new/`／`out/`，舊 fsm 範本就對不上通用接口。** agent-bob／ann／dan、topdown 的腦與 fsm 直接讀工作區的 `new/`；P-11 的 10-29 加註又說「照舊用，新東西才走標準」。**後果**：不遷＝這些範本只能手放題目、`aos-exec` 跑，`aos-chat agent-dan` 這種用法沒了（test_human 要改用新的假 agent）；遷＝十幾隻 demo 的 brain.py／fsm 都要改，一兩天。**建議**：不遷、標舊協議，等真要用到那隻再遷（見方向題 1）。 **已定：照建議（使用者 10-30「都照建議」）。**
5. **queue 的一則訊息＝OpenAI message，跟 N-16「`body` 形狀由收信程式定」合、但跟「給人用」有點硬。** 人用 aos-say 說一句話，say 替他包成 `{"role": "user", "content": …}`；有人想直接 `aos-post send` 投一句純文字就是壞信。**後果**：只收 message 物件＝agent 不用轉換、history 一行一行對得上；也收純字串＝多一條「字串＝user 的 content」的暗規則（C-56 不藏規則）。**建議**：只收 message 物件，人一律經 aos-say。 **已定：照建議（使用者 10-30「都照建議」）。**
6. **停著等的 agent 對 `paused`／`stopped` 的反應最多慢一個 `interval_ms`。** aos-loop 只在兩次之間讀 ctl；`ROUND_ON_EMPTY=idle` 時 round 每次退 0、loop 隔 `interval_ms` 再起。**後果**：不在 round 裡阻塞等信＝程式最簡單、反應時間＝`interval_ms`（範本給 300 毫秒）、空轉時每 300 毫秒起一次行程；在 round 裡等＝反應更即時，但暫停要等它等完那段才生效、多一段阻塞程式。**建議**：不阻塞，照上面。 **已定：照建議（使用者 10-30「都照建議」）。**

## 方向題（原則推不出的，附背景例子）

1. **舊的 fsm 範本（agent-bob／ann／dan、topdown 兩隊）要不要一起搬到 queue？** 背景：它們是 10-19～10-25 的範本，腦跟 fsm 直接讀工作區 `new/`；aos-say／listen 改走 queue 之後就說不到它們。agent-dan 是 P-41 腦的工具呼叫的範本，10-28 起新範本是 agent-nia（round）。**建議**：不搬，P-11 標舊協議；哪隻真要再用（例如場景二拿 fsm agent 試「暫停改東西」）就只搬那隻。 **已定：照建議（使用者 10-30「都照建議」）。**
2. **daemon 的 `execs` 子項退了之後要不要讓 state 列留著？** 背景：loop 型子項 `done` 之後列留在 `loops_state.json` 上直到名單拿掉；一次性的 exec 子項會很多（每個射後不理的 agent 一列），表會越來越長、超過 100 列就切分頁。**建議**：跟 loop 型同一條規則（留著，名單拿掉才消失）——規則只有一套（C-52 同一把尺）；表長是使用者自己把名單清乾淨的事（同 P-14 `done/` 清理是人的事）。 **已定：照建議（使用者 10-30「都照建議」）。**
3. **外部 CLI 的 session 檔，hub 只替「hub 自己開的」實例留，還是也替 agent 當工具叫的 claude／codex 留？** 背景：agent 的 act 經 cli_session 叫 claude 工具時會 `register` 進 hub（只登記），那次的 session 檔同樣在 `~/.claude/projects/`；留＝每次工具呼叫的小格都多一個 symlink；不留＝只有 `aos-hub add／open` 的實例有。**建議**：都留（建 symlink 零成本、知道 id 的地方同一處），stop 時才複製的只有 hub 管的實例。 **已定：照建議（使用者 10-30「都照建議」）。**

## 決定（10-30）

使用者看完衝突六條與方向題三條，原文「都照建議」。九條各一句（連回上面各條）：

- **衝突 1**：queue 放 `$AOS_STACK/queue/`，C-65 括號裡的例子改口（對話是執行狀態、不是成果）。
- **衝突 2**：替黑盒子留 session 檔不進 NORMS，寫在 hub 說明與 CONVENTION 的 adapter 段；決定 26 不動。
- **衝突 3**：做 daemon 原生 `execs`（②），N-28、N-54 照草稿補；`max: 1`（①）留著當底層與過渡。
- **衝突 4**：舊 fsm 範本不遷、P-11 標舊協議，aos-say／listen 不再認它們。
- **衝突 5**：queue 只收 OpenAI message 物件，人一律經 aos-say。
- **衝突 6**：停著等不在 round 裡阻塞，暫停反應時間＝`interval_ms`。
- **方向題 1**：舊範本不搬；哪隻真要用（例如場景二的 fsm agent）才只搬那隻。
- **方向題 2**：`execs` 子項退了以後 state 列跟 loop 型同一條規則（留著，名單拿掉才消失）。
- **方向題 3**：工具叫的 claude／codex 也留 session 檔 symlink；stop 時才複製的只有 hub 管的實例。

## 實作時代定（10-30，隊長與工人照原則定的細節，可翻案）

另外兩件也在這輪做了，是使用者 10-30 加的：aos-kernel-llm 改名為 aos-llm-kernel（c0e6c01c），aos-gate 改名為 aos-llm-send（f9fc45ae）。前綴代號：Q＝queue 線（第 1～5 步）、D＝daemon 線（第 7、8 步與 aos-daemon-ctl）、T＝條文（第 10 步）、R＝改名。

### 第 1～5 步

- **Q-1** claim 的順序是：先 `aos-post claim`，再把 body 接進 history，最後寫 `current.txt`。`current.txt` 記的是「已經接進 history 的信」；`cur/` 裡有信卻沒列在上面，表示上次死在中間，下次 claim 先把它補完。理由：aos-post 不能指定要認領哪一封，先看再接會碰上撤回。
- **Q-2** queue push 的 stdin 是一則 message JSON，不收純文字，也不收題名。信號由 aos-post 給（衝突 5）。
- **Q-3** pop：信不見了，就印 history 最新那則沒有 `tool_calls` 的 assistant。history 裡沒有 assistant 時：看到過這封信＝`AnswerMissing`，從沒看到＝`LetterUnknown`（A-6：不保證一題配一答）。
- **Q-4** 壞信，就是不是有序的名字、`aos-post check` 不過、或 body 不是 message。處理法是 `aos-post finish` 丟掉，不寫 stderr。round 的 `letter_warning` 還沒做。
- **Q-5** queue 的 finish 不看 stdin（答案在 history）。
- **Q-6** 代號改用 `Letter*`，對齊 aos-post；新增 `PostFailed`。queue 只要 `AOS_STACK`，不再查 `AOS_WS`。
- **Q-7** claim 時沒掛 history 格＝`PartMissing`，信留在 `new/`。
- **Q-8** round 碰到「`cur/` 有信沒列進 `current.txt`」＝補認領，而且不叫 `pre_round`（同一次認領不重做那一步）。
- **Q-9** round 拿掉 `WsMissing`，只用 stack。`ROUND_ON_EMPTY=idle` 時 queue 空：退 0，連 trace 都不寫，`--step` 也一樣。值不對＝`SettingBad`。
- **Q-10** act 的插話改看 `$AOS_STACK/queue/new/`，`on_interrupt` 的 stdin 改成信號（照 A-9 推過來）。
- **Q-11** Spawn 的測試不再經 aos-ai。agent-nia 範本：`max: 40` 搭 `stop`；README 裡停著等的那份定義拿掉 `max`、加上 `interval_ms: 300`。
- **Q-12** ask_round 判斷答完沒，是叫 `queue pop --timeout-s 0`，不自己看資料夾（C-52）。
- **Q-13** listen 判斷服務者失敗：看 trace 最後一行，`code` 不是 0、10，或有 `signal`，就算失敗。格名先取 `unit`（round 的寫法），沒有再取 `state`（fsm 的寫法），說成「停在 X 那格、結束碼 N」。chat 用同一句。
- **Q-14** say 去掉 content 結尾那一個換行。`--last`／`--follow` 一段的格式是「== #N」，問的話每行前面加「> 」，再接回答。上一則回答之後的 user 都算這段的問題。
- **Q-15** 判斷有沒有服務者：先比行程環境的 `AOS_STACK`；沒設的，只在它用預設的 `<ws>/.stack/` 時才比 `AOS_WS`。
- **Q-16** aos-ai 跟著 aos_ws 改走 queue（隊長代定「甲」，照衝突 4 推過來）：
  - ask 拿掉 `--id`；run 回 `answers`，不帶 id，另外回 `answered`；spawn 預設範本改成 agent-nia。
  - 後果：舊 fsm 範本只剩 `run` 能用，題目要手放 `ws/new/`。
  - nvim 外掛的 `use_say` 預設改成 false，因為外掛編出來的是 fsm agent。

### 第 7、8 步與 aos-daemon-ctl

- **D-1** `execs` 不收單子物件，收了＝CfgBad；要跑單子就寫 `daemon.json#/…` 指過去。
- **D-2** `{"exec": 目標}` 形式的其他 key 都忽略，例如 `max`（C-48）。
- **D-3** 相對的目標不轉成絕對：子行程會先 cd 到 daemon 的 cwd。
- **D-4** 換種類（同一個名字 removed 再以另一種 added）＝收掉舊的，下一圈起新的。
- **D-5** 合出來的期望表兩邊同名：loops_ctl 整份不採用；信箱模式的信＝壞信，記 `letter_warning`、不回信。
- **D-6** `loops_state.json` 一律有 `execs`，沒有就是 `{}`。分頁跟 `loops` 共用 `loops_state_loops/`。
- **D-7** adopt 碰到 10-30 以前沒有 `execs` 欄的 state，當成空的。
- **D-8** 命令列名字叫 `aos-daemon-ctl`（使用者原話「或許是aos-daemon-ctl add XXX這樣」）。放在 proto8/bin、用 Python 寫，跟 aos-tools、aos-parts 同一類；子命令 add／rm／ls。
- **D-9** 用哪個 daemon，照 N-63 的 hub 型變數：`--daemon` ＞ `AOS_DAEMON`，值＝那個 daemon 的 `$AOS_STACK` 資料夾，都沒有＝`DaemonMissing`。窗用預設名字（`loops_mailbox/`、`loops_state.json`）。
- **D-10** add／rm 是往信箱模式投信（N-54 的 10-29 補：多人改名單就開信箱模式），不去讀改寫 loops_ctl。daemon 不是信箱模式＝`MailboxMissing`。
- **D-11** rm 一封信同時寫 `loops_removed` 和 `execs_removed`。
- **D-12** 自動識別只看「XXX 是資料夾，而且裡面有 loop.json」，`_entry` 不解析。是 loop 的話，把它的 loop.json 搬成子項設定：去掉 `_entry`；相對的 exec 轉成絕對；單子沒寫 cwd 就補 XXX。`.env`、`$ref`、`$env` 不處理。其他情況一律＝`execs`。
- **D-13** `--kind loop|exec|max1` 可以蓋過自動識別；`max1`＝`{"exec": XXX, "max": 1}`，是使用者說的底線。
- **D-14** 名字取 `--name`，沒給就用 XXX 的資料夾名。名字合不合格、撞不撞名由 daemon 驗。add 只印信號，不等 daemon 套用。
- **D-15** ls 一行是「名字 TAB loop|exec TAB phase TAB pid TAB code」；`--json` 印一整行。
- **D-16** demo/daemon-3 改成信箱模式，好讓 README 能示範 aos-daemon-ctl。

### 第 10 步條文

- **T-1** P-42 只落 ①～③（queue、history、ctl／state）和 `ROUND_ON_EMPTY`；④ `server.txt` 與 hub／外部 CLI 那句暫緩。
- **T-2** N-28 只用一句指到 aos-daemon-ctl，用法留在 bin README；`AOS_DAEMON` 寫成 N-63 的一個實例。
- **T-3** 「直接 aos-exec 的歸 Linux 管」寫成 N-28 底下另一條補。沒塞進開頭那段「不管」，因為那段是使用者 10-22 列的清單。
- **T-4** 這幾處還是舊說法、沒改：NORMS/08 第 7 行、P-19 的「idle 看 `new/` 空了」、P-41 的「題目還在 `cur/`」。它們多半屬於舊協議（見 WAIT_USER）。

### 改名

- **R-1** demo 資料夾跟著程式改名：`demo/kernel-llm` 改成 `demo/llm-kernel`。環境變數 `AOS_KERNEL*` 不改。
- **R-2** NORMS 正文照 NORMS.md 第 16 行的規矩：只換名字、不留舊名。10-25 那批的歷史敘述照留舊名。
- **R-3** thinking／topdown 的舊紀錄只改 5 個連結的目標，字不改，為了讓 wf-lint broken=0。

### 使用者問：round 能不能放在 aos-loop／fsm 的框架下實現（10-30，只查、沒改）

**拼得出來，但 round 會散到每一格裡；要乾淨得先改規範，這是方向題。** agent-dan 已經是這種形狀：loop 跑 fsm，idle 格 queue 空了退 10，loop 就停。

- **對得上的**：
  - idle 空了退 10、loop 停；
  - `--step`＝fsm 一次跑一格；
  - `hook/pause` 可以換成 aos-loop ctl 的 `paused`；
  - 格可以經 `aos-parts run` 叫。
- **對不上的**：fsm 每格只有一個 `next`（N-36），只有退 0 才前進，退 10 是往上傳、讓 loop 停。round 要的分支、「成功但留在原地」、「前進完就停」三樣，fsm 都沒有。所以只能排成一條直線（idle → claim → think → act → finish），每格自己再判一次「這次該不該做事」，think 那種一步串好幾格的還得另寫小腳本。
- **做不到或很彆扭的**：
  1. `ROUND_ON_EMPTY=idle`：退 0 會前進、退 10 會停，只剩阻塞等，可是衝突 6 已經定了不阻塞。
  2. 插話：act 退 10 本來是「被打斷，正常」，到了 loop 卻變成停。要包一層轉碼，再加一格和一個記號檔。
  3. 「答完一題就停」（ask_round 靠它）：做不到，只能答到 queue 空才停。
  4. `on_error` 的 retry、switch、`MAX_RETRIES`：fsm 碰到非 0 不重來。而 N-38 寫的是「重試幾次看外面的 loop」，跟 round 自己數相反。
  5. 可有可無的 hook，以及「補認領不叫 `pre_round`」：要在格裡自己判。
  6. trace 撞檔：fsm 的行是 `{"state"}`、round 的是 `{"unit"}`，會寫進同一個 `trace.jsonl`。
- **要乾淨的兩條路，都要改規範，給使用者選**：
  - 甲：fsm 的 `next` 照結束碼分岔（例如 `{"0": "act", "11": "finish"}`），要改 N-36。
  - 乙：多一個「成功但留在原地」的結束碼，要改 N-43。
  - 兩條都不走的話，round 留著當骨架最省：它本身就是一支「看資料決定下一格」的 fsm，loop 只負責反覆叫它（idle 加 `interval_ms`），就是第 2 步做出來的樣子。
