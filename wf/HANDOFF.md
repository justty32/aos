# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 深夜（家機，使用者在場、準備玩 aos）——知識庫整庫換成「md 為主體、index json 做骨架」做完；API agent 認 `/clear`；沒有線在跑；活樹裝到 `fe053b828`；今天的 commit 都沒 push

> **session 已關，使用者改用 `~/aos-home` 的 eca_main**（11-21 深夜收工整理，線 `top-1121-wrapup`；使用者原話「所以應該沒事要做了吧，那你按照wf/規矩整理收尾。之後我把這個session關掉，開aos home，用eca main了」）。下一個接手的是冷啟動：下面「只限這個 session」的授權已失效，要用得重新問；這個 session 派過的子 agent 都叫不回來了。下面「等他說的」幾題已另記進 `wf/progress.json` 的 `waiting-1121`。

**使用者今天開場的指示（逐字）**：「事情盡量交給agent做，你就負責跟我交流。普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前也要讀過wf/規矩，簡單工作與雜活除外。agent可以再派agent，模型隨意。用繁體中文跟我說話。」**現在沒有 goal。**他今晚自己玩 aos，有問題會來問。

**授權（11-21 當場；只限這個 session）**：
- push：沒給 → **不推**。本地領先 origin 約 128 筆（含收工整理那筆）。
- `~/aos-home`：已更新七次（紀錄 `aos-home-更新-1121.md`，最後 `198719adc`，裝的是 `fe053b828`；ann 的 `system.txt` 換成新範本、入口 `_description.md`）。他說過「我還沒開始玩aos，可以動樹」是當下那一次；**再裝之前仍先問他、確認樹停著**。
- 刪檔：只限已做完的那幾批（知識庫被 md 取代的舊 json）。不延伸。
- 他會擋看不懂的長指令 → 指令一次一件事。子 agent 的 `commit-request submit` 被擋不要繞。
- LiteLLM（localhost:4000）是他起的，不停不改。
- 活樹的 `AOS_HOME` 就是 repo 的 `proto8/`：`knowledge/`、`frontend/`、`templates/`（含 agent-fsm 的格程式）**存檔即生效**；動 `py/`、`cpp/` 要 `install.py`。

**還在跑的線**：沒有。fable 隊長線 `top-1121-kbmd` 五段都交了；session 關了，它的 agent id 叫不回來，要續做就照規劃夾重開一條線。

**今晚做完的大事：知識庫換樣子**（規劃與紀錄全在 `proto8/thinking/2026-11/21/知識庫-骨架加md-規劃-1121/`，他的 25 句原話逐字在 `00`、`08`、`09`、`11`、`15`）：
- 現況：`proto8/knowledge/` 的 `aos/`、`wf/` 兩庫所有頁都是 `.md`，只剩 4 份夾的 `_index.json` 是 json。入口 `knowledge/aos/_description.md`。commit：工具 `6c769595d`、aos 庫 `fe053b828`、wf 庫 `33835099a`、最後 5 頁與 repo 規矩 `578a7c762`、code map 補洞 `00d156173`／`084fa0306`。
- 尋址（全文 `07-尋址規則.md`，知識庫 `docs/03-md頁與尋址.md`）：`x.md#/標題字` 拿一節；`#/標題/_` 標題自己的內文（保留名只認 `_`）；`#/標題/0` 第一個清單的項、`鍵: 值` 清單可用鍵尋；表格 `#/標題/列/欄`（表頭是第 0 列、值一律字串）；清單與表格同節只認清單；標題底下只有一個 json 區塊就當 json 往下尋；md 裡不加任何標記。自動跟到 md 只用 `$ref`。json 工具不寫 md。
- index：`_index.json` 一項可以是純字串（＝description）；`index` 欄可指任何「檔#/路徑」（含指進 md）只要讀出來是 index 格式；沒有 `_index.json` 才看 `_index.md`；md 認 `# index`／`# description`（也認底線版）。`index_check` **整支重寫**成九條（清單在 `10-index_check.md`），「要列出夾裡每一個東西」那條刪了。
- 轉換腳本 `wf/tools/kb_md.py`（原樣搬文章）、`wf/tools/kb_md_shape.py`（換形狀）；對照表 `kb_md_map*.json` 在規劃夾。
- 「新寫的預設寫 md、index json 做骨架、兩種都可以、不做檢查」已寫進知識庫說明六處與 repo 規矩六處（鐵律 6、rules-card 6、`data-files.md`、STRUCTURE/02、04、N-45），都是原字不動加一句（`17`、`19` 兩份改前改後）。
- 中文映照版 `proto8/knowledge-zh-md/`：只重寫了 4 份 `_index.md`；內文的舊路徑、`#/鍵` 標籤、README「正本是旁邊的 json」都還是舊的。

**API agent 的 `/clear`**（`ef774a4a3`，線 `top-1121-apiclear`，紀錄 `api-agent-clear-1121.md`）：agent-fsm 收到剛好是 `/clear` 的信不叫模型、history 搬進 `history_removed.jsonl`、只留這一問一答。改的是 `templates/agent-fsm/`，不用重裝。API 這邊 `/compact` 11-20 起就有；`/status`、`/usage`、`/exit` 沒有。只用假模型驗過，沒在活樹跑過。

**等他說的（已念給他、沒答，不催；前四題 11-21 夜已答，見下）**：
- 已答（11-21 夜，原話在規劃夾 `15` 第 26 句）：4 份 `_index.json` 留 json、做骨架；description 太長時可在 `_index.md` 補充、用 `$ref` 指過去（已寫進知識庫 `docs/03`）。repo 自己 `wf/` 的 json 資料檔先不轉。
- 已答、已記待辦、之後改：拿不準沒動的條文（N-62、N-69、C-42 續、`tidy/README` 第 4 條、`wf/public/整理與拆檔.md`、`proto8/docs/` 2 處舊路徑）；中文映照版 `knowledge-zh-md` 內文整份重做。兩條都在 `wf/progress.json`。
- API agent 要不要 `/status`、`/usage`、`/exit`。
- 新 `index_check` 他說過「之後要看看」。
- 換形狀比較醜的頁：`wf/source/block-3.md`、`block-4.md`。

**今天稍早聊出來、他還在想的（原話都逐字在對應 thinking 檔，不催）**：
- shell 比喻：`shell-指令的比喻-1121/04`、`05`。
- kernel 攔截 daemon 存取：`kernel-攔截daemon存取-1121/`；桌面 `aos-kernel攔截daemon存取-1121.html`。原則：「只防走規矩的存取，不守規矩的就是要自己承擔風險。真的要硬防，那就要多依賴linux的權限體系」。
- 權限零件：桌面 `aos-權限零件-1121/`。
- 驗寄件人：`驗寄件人-規劃-1121/`，他答 1D、2C、3C、4A，要自己開沙箱試；頂層沒派施工；另五題沒念。
- 前端大修盤點 14 項（`frontend-備妥-1121.md`）沒念；程式旁文件對不上幾處（`share/README`、`asuser/README`）沒改。
- 更早等他的：gpt 包預設走 `/v1/responses`；`history set` 收不收 `-n`；N-63 加註；stack 要不要記定義夾與工作區；eca 三包要不要瘦；條文整體大修；kernel 編譯「我之後再來玩」。

**今晚他用的東西**：
- eca_main：`proto8/docs/tutorial/05b-起eca_main.md`（最短路 01、02→05b）。
- 前端：起樹後另開視窗 `cd ~/aos-home`、`AOS_DAEMON=~/aos-home/.stack aos-frontend serve`，頁 http://127.0.0.1:8768/ 。
- ann 的 history 裡還有舊 `.json` 路徑的對話，它照記憶查會「檔不在」；寄 `/clear` 或跟它說入口換了。

**記給公司機的**：刪 `~/code/rv`（刪前再確認）；GitHub 的 `rv` 他自己刪；公司 WSL 要重裝並照 `hook-新格式施工-1121/03` 搬；知識庫換成 md 後公司機 pull 完要重裝、樹裡抄進去的系統文字入口要換。

**暫存夾留著的**：`~/.aos/scratch/top-1121-*`（`top-1121-kbmd/` 很多份複本）；`top-1121-ownerplan/exp/owner/` 要 `aos-asuser --fix` 才清得掉。

**派線的做法（家機）**：Agent 工具派 Claude 子 agent（普通 opus、雜活 sonnet、他點名才 fable）；任務書寫明：先讀知識庫入口 `proto8/knowledge/aos/_description.md` 與規矩卡、線名 `top-1121-<名>`、乾淨複本＝`git archive HEAD` 解到 `~/.aos/scratch/<線名>/`、這台沒有 pytest 用 unittest、不在 repo 跑 `install.py`、不碰 `~/aos-home`、清 `AOS_*`、收行程只准兩種、不開 tmux、不印環境變數、不刪檔不 push、交件走 `commit-request`（`claim` 的檔是位置參數；`submit --files`）、背景等待腳本用完自己收（別用會認到自己的 `pgrep -f` 迴圈）。回報先 `git show --stat` 核對再轉述；它替使用者做的選擇逐條念給他聽。頂層記他的原話時追加進對應的 thinking 檔、用線名 `top-1121-home` 交。

**坑**：
- 問句不是指示；一句話兩種讀法先標出讀法再做；他補一句就可能翻掉前一句（今晚 `_index.md` 合併→有 json 就不看、純字串指向→純字串＝description 都發生過），轉給線時原話逐字附上。
- 頂層憑舊紀錄答事實會錯（今晚說「`/compact` 只有 eca 認」「做完要重裝」都被線查出不對）→ 沒查過的事講明是推測。
- 選項框不標推薦；最多四題、每題最多四個選項。
- 說話：kernel、daemon、llm kernel 直接叫；handle 說「遙控器」；「編譯／重新編譯」「靜態連結／動態連結」。
- 這台 `ls` 是 `eza --git`，在背景指令裡會卡住。
- 子 agent 不要開 tmux（會觸發他的自動復原外掛）。
- 知識庫、前端、範本存檔即生效：他在玩的時候往這三處寫檔要一次寫完整。
