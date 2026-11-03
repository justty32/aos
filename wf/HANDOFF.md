# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-03 傍晚下班（公司 Windows；回家開新 session 接）

1. **授權**：同 13:30 那條（隨意 push、opus／sonnet／fable 分工、agent 先讀 wf 規矩）；新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。多個 agent 同一工作樹時，各自用 GIT_INDEX_FILE 暫存 index 只 commit 自己的段，今天沒再出事。
2. **13:30 之後做完並 push**：WSL 試驗場 `~/code/playground` 重建（clock、bob、cathy、bob-cathy、resident_bob、eca_bob、eca_kit、kit 工具箱、README 一步步實跑）；說明頁 https://claude.ai/artifact/9k9ssEvEQiKDBcUFmrAZJ9 （第 3 版；舊親手試指南沒覆蓋）；收尾四件 `c7475734`；eca 接 aos 工具（`c024c974` 規劃、`7f363fd4` 實作：eca 資料夾的 tools.json，cli.json `tools` 可改指，使用者「如果cli.json沒有指定，那就去找默認的tools.json」）；aos-eca ls／state 英文名詞＋畫面欄 open／closed（`04b0f33d`，eca 19）；eca 信交給 CLI 就收（`a0bbb2ac`，eca 20；使用者「對於eca來說，他收到信後，丟給claude之類的，然後這封信就算是完成了」「中途掛掉就是邊緣狀況，不要讓邊緣狀況影響他的原本意思」；current.txt 拿掉；P-12／P-43 加註）；`aos-tools add --no-cache`（`dcca4a8c`，aos-tools 04）。
   - **已驗（11-03 晚家機 Manjaro 暫存 clone）**：三個 commit 合跑全套 unittest 646 OK（9 skip）、demo 0、ctest 8/8、wf-lint broken=0。
3. **daemon 收工 sleep／wake：已實作、使用者 11-03 晚看過定案**（不開放 sleep／wake 指令；出錯退出走同一條收工路、再開自己醒＝合他「輕鬆回復原本狀態、收斂錯誤處理路徑」）（[procs § 8](../proto8/thinking/2026-11-03-procs.md#8-收工時改寫成休息中sleepwake11-03-晚)）。使用者「改寫成休息中」「還記得嗎？我們有start/stop, sleep/wake, pause/resume，我們缺了sleep/wake」。照頂層代定做：收工（ctl stop／Ctrl+C／任何走 finish 的退出）時還在跑的 loop 型＝表上 `sleeping`、stack 留著；daemon 再開 adopt 後第一圈用列上的 stack 自動 wake；你 stop 的照舊 `stopped`；收工時暫停中的醒來仍暫停（已實測）；exec 型照舊拿掉；`kill -9` 不在範圍；`aos-daemon-ctl sleep／wake` **先不開放**（原本待他答的 (a)，代定「不開」）、(b) 照建議「醒來仍暫停」。睡著時寄來的 stop＝開門改 stopped 不 wake、rm＝拿掉。
4. **雜項**：
   - WSL `~/repo/simple_tools/aos` 在 `dcca4a8c`，但有一個不知誰改的追蹤檔改動 `proto8/lib/aos/ask_round/_tooldef.json`——問使用者，之後 ff 前先處理。
   - Windows 工作樹 `proto8/thinking/README.md`、`months/2026-11.md` 兩檔舊未 commit 改動（比 HEAD 舊）等使用者確認丟掉。
   - 試驗場 `daemons/main` 的 stack 在 `ws/.stack`，eca 在 ws 裡看得到整個 daemon 內部；提議移出工作區，使用者還沒回。
   - WSL `~/.codex/config.toml` 預設模型 `gpt-6.1-sol` 這帳號不能用（model_not_found），使用者的設定、沒改。
   - 常駐 bob：使用者「感覺之後會被蛋雕」「先不用管吧」。
   - 使用者之後要看 aos-post（impls/aos-post）。

## 2026-11-03 13:30 出門前（公司 Windows；下次開 session 接）

1. **授權**：本 session 隨意 push、普通事 opus、簡單與雜活 sonnet、規劃 fable、做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。下次開新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。工人只 `git add <明確的檔>`，不 checkout --／restore／stash／reset／-A（今天有 agent 用 checkout -- 抹掉別人未 commit 的改動）。
2. **今天做完並 push**（細節看各 thinking 檔末「實作時代定」）：aos-eca-hub→aos-eca（單隻、`add [--name N] [--ws WS] [--stack S] XXX`、rm、撞名報錯、ls 暫留）；trace.jsonl 整個拿掉；state／status 兩個指令都收；eca-turn 一批信一起丟；topdown 封存；ws 不放 `.stack` 捷徑、`aos-daemon-ctl where --stack 名字`；`aos-exec --stack`；loop ctl.json 改下指令 `{"cmd": pause|resume|stop}`（`4b2d6d86`）；execs／loops 合成 `procs`，每項可寫 `stack`，aos-daemon-ctl 有 add／rm／start／stop／pause／resume（`b248ed02`）。全綠：unittest 634 OK／13 skip、ctest 8/8、demo 0、wf-lint broken=0。
   - **要跟使用者講的行為改變**：eca 自己出錯結束或有人直接寫 stop 到它的 ctl，會從 daemon 表與 `aos-eca ls` 消失（procs 衝突 2「照舊拿掉」）；要接著用就同名再 add、同一個 stack，對話接得上。
3. **下次要接的**：
   - 整理 WSL `~/code/playground`（11-03 已清空）照新設計重建：手改清單在 WAIT_USER；刪 amy；然後做「玩 playground」說明頁（使用者：「在去幫我弄artifact吧，這樣我之後玩playground時更舒服」），可更新親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 。
   - 工作樹留著 `proto8/thinking/README.md`、`proto8/thinking/months/2026-11.md` 兩檔未 commit 的舊版文字（比 HEAD 舊、非今天改的），請使用者確認後丟掉。
   - 小事：aos-loop `ctl_note_` 沒人用；`demo/talk/team/quiet.py` 自拼 `procs/<名>/state.json`；`aos-ai exec --stack` 沒傳給 aos-exec；6 個 code map 檔 >8 KB（開發期先不拆）。
   - 以後：say／listen 改成 `aos-agent` 體系、agent 在工作區建 `.aos/agent/`（使用者「之後還要再改」）；aos-eca-hub（繼承 daemon）管多隻 eca；瘦身候選 aos-chat、aos_ws.loop_state、nvim 外掛。
4. **artifact**：eca 圖解 https://claude.ai/artifact/1DW3vC6ENR4VWUfGs7qXco 與其他 11-02 的頁都已過時。

## 2026-11-02 晚收工（家中 Manjaro；明早開新 session 接）

1. **授權**：今晚隨意 push、普通事 opus、簡單與雜活 sonnet、規劃 fable、做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。**明早開新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問一次**。頂層 Bash 裡 `ls` 寫 `/bin/ls`。工人只 `git add <明確的檔>`、不 `-A`、不 force／reset、不碰 stash——今晚多個 agent 同一工作樹 commit 時兩度把別人 staged 的檔帶進去，commit 前一定 `git diff --cached --stat`；子 agent 的完成通知會送到頂層、不送給派它的隊長，頂層要轉。家機試驗場 `~/code/playground`（不在 git）今晚重建：env.sh、agents/bob、agents/resident_bob、agents/eca_bob、daemons/main；`daemon_ws/` 是使用者自己開的 daemon，別碰。
2. **今晚做完並 push**：公司 33 個 commit 快轉；digest 舊字樣（`721bdc46`）；aos-listen 翻案（`4fcc483f`，只留 `aos-say … && aos-listen`）；compact `endpoint` bug（`e31f7921`）；eca 盤點與「收工了」（`53f1d6b6`、`b11987f0`、`983a2632`）；**aos-eca-hub（11-03 改名 aos-eca-ctl（同日再改 aos-eca））三對指令** open／close、start／stop（stop 留小格）、add／remove（remove 刪小格、不封存），reap 自動掛 `eca_reap`（`bd0f3d4a`，代定 11 條在 [eca 15](../proto8/thinking/2026-10-30-eca/)）；`letter_warning`→`mailbox_warning`（`c8ac6bfc`）；刪 demo agent-dan、agent-dan-q（`7dcc3dc6`，假腦小幫手搬 `tests/fake_brain.py`）；ctl/state 規劃（`bdf9283a`，[ctl-state-names](../proto8/thinking/2026-11-02-ctl-state-names.md)）與實作（`971811ce`＋`5a6b600f`：daemon 自己的窗改回 `ctl.json`／`state.json`、常駐 bob 控制器同、aos_ws 只認 `state.json`；全套 800 OK／11 skip、ctest 8/8）。使用者親手玩 hub 畫面：「體驗不錯」；常駐 bob「等之後有空」。eca 圖解 https://claude.ai/artifact/1DW3vC6ENR4VWUfGs7qXco （第 2 版；三對指令已實作、reap 已會自動掛，頁面還寫「還沒實作」，要更新）。
3. **明早要接的**：
   - **整體瘦身**（使用者：「明天早上再說，或者我們這樣子一點一點的，也算是了」）。候選清單：`demo/llm-kernel`、`demo/self-improve`（使用者「完全沒有印象」「明天應該會刪掉」；刪了環境變數第 4 題的 `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN` 就消失）；Lua／Janet 的 `agent_dan` 範例與 nvim 外掛的 smoke（讀已刪的 agent-dan，測試先 skip，待使用者定）；10-23 agent-dan artifact。
   - **proc 改名想法**（ctl/state 方向題 1，未定）：使用者「exec和loops，其實都屬於proc，所以...改名？…exec是基石，loop是另一種基本形式，搞不好以後還會有更多形式」；今晚 `loops_ctl`／`loops_state` 不動 → [ctl-state-names](../proto8/thinking/2026-11-02-ctl-state-names.md)。
   - **amy 刪掉**（使用者「刪掉」）：公司 WSL `~/code/playground/agents/amy`，WAIT_USER／SESSION-LOG 相關條目若今晚沒清就清。
   - eca 以後再優化：每封信 `--resume` 起退、依資源縮短閒置（使用者「以後再說」）→ eca 14。
4. **artifact**：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt （11-01 版，今天 11-02 的改動還沒回寫）。

