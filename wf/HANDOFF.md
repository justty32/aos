# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-03 晚收工（家機 Manjaro；明天開新 session 接）

1. **授權**：今晚隨意 push、普通事 opus、簡單與雜活 sonnet、規劃 fable、做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent；新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。commit 一律 `git commit --only -- 路徑` 或 GIT_INDEX_FILE 暫存 index（今晚頂層一次不帶路徑的 commit 把 tidy 兩批包走：eb4dea91）。
2. **今晚做完並 push（main）**：三 commit 合跑全套已驗；daemon 收工 sleeping／開門 wake（`68c4e258`，不開放 sleep／wake 指令）；wake 後 ws 欄修好、`--enable-logs` 與 Ctrl-C 收工寫進 README（`6d42a264`）；封存瘦身候選到 `proto8/archive/`、刪 agent-fay（`c3cbf617`）；刪 round 那套 agent 與 aos-ai 只留概念（`cb6b49e0`，`proto8/archive/agent-round-concepts/`；aos-mcp、aos_ws、aos-say／listen 留著，使用者選「先留著」等 aos-agent）；tidy 收斂多批（W0～W4、P5、N-28 與 P1-1 摺 NORMS、P4-A～C thinking 精簡，狀態全在[收斂報告](workflows/tidy/reports/2026-11-03-收斂.md)）；家機試驗場 `~/code/playground` 清空重建成只玩 eca（daemon＋bob〔claude haiku、clock 工具〕，README 一步步）；aos-eca-turn 手冊頁 https://claude.ai/artifact/GsAZQHDCN7wHDUP3vvS78h 。
3. **明天要接**：
   - **aos-post 改版**（使用者「都照建議」，[thinking](../proto8/thinking/2026-11/03/aos-post/README.md) 檔末「實作進度（11-03 晚收工）」）：步驟 1～8 已在 main（`5e2fe35e`，已 push）。**併進 main 時沒跑驗證**（使用者「不用測試，總之先弄進去」），明天補跑全套與主工作樹 impls 重建（試驗場用的 bin 還是舊版）；剩步驟 9 條文加註（N-14～16、C-48、C-54 `…Exists`、P-42／P-43）、10 的舊名 grep 檢查。
   - **tidy 收斂**：照報告接；P4-D／P4-E 12 份 thinking 精簡未對讀就進了 main（`6c960429`，使用者「不對讀，直接進 main」「反正有需要的話再去翻舊的commit」），明天補對讀；P2 CONVENTION 的心得已記報告；NORMS 05（N-14～17）與 C-54 等 aos-post 加註完再摺；round 已刪後沒實作對應的條文清單在 SESSION-LOG，要給使用者看。
   - 使用者說「明天我通勤時候看」：aos-eca-turn 手冊頁。
4. **雜項**：試驗場兩個 daemon 同資料夾＝使用者「這是使用者自己要承擔的風險」；寫 ctl.json stop 同內容第二次不生效＝使用者選收工用 Ctrl-C。公司那邊：WSL clone 裡 `ask_round/_tooldef.json` 的改動直接丟（ask_round 已刪）、Windows 兩檔舊改動丟掉、`agents/amy` 刪。

## 2026-11-03 傍晚下班（公司 Windows；回家開新 session 接）

1. **授權**：同 13:30 那條（隨意 push、opus／sonnet／fable 分工、agent 先讀 wf 規矩）；新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。多個 agent 同一工作樹時，各自用 GIT_INDEX_FILE 暫存 index 只 commit 自己的段，今天沒再出事。
2. **13:30 之後做完並 push**：WSL 試驗場 `~/code/playground` 重建（clock、bob、cathy、bob-cathy、resident_bob、eca_bob、eca_kit、kit 工具箱、README 一步步實跑）；說明頁 https://claude.ai/artifact/9k9ssEvEQiKDBcUFmrAZJ9 （第 3 版；舊親手試指南沒覆蓋）；收尾四件 `c7475734`；eca 接 aos 工具（`c024c974` 規劃、`7f363fd4` 實作：eca 資料夾的 tools.json，cli.json `tools` 可改指，使用者「如果cli.json沒有指定，那就去找默認的tools.json」）；aos-eca ls／state 英文名詞＋畫面欄 open／closed（`04b0f33d`，eca 19）；eca 信交給 CLI 就收（`a0bbb2ac`，eca 20；使用者「對於eca來說，他收到信後，丟給claude之類的，然後這封信就算是完成了」「中途掛掉就是邊緣狀況，不要讓邊緣狀況影響他的原本意思」；current.txt 拿掉；P-12／P-43 加註）；`aos-tools add --no-cache`（`dcca4a8c`，aos-tools 04）。
   - **已驗（11-03 晚家機 Manjaro 暫存 clone）**：三個 commit 合跑全套 unittest 646 OK（9 skip）、demo 0、ctest 8/8、wf-lint broken=0。
3. **daemon 收工 sleep／wake：已實作、使用者 11-03 晚看過定案**（不開放 sleep／wake 指令；出錯退出走同一條收工路、再開自己醒＝合他「輕鬆回復原本狀態、收斂錯誤處理路徑」）（[procs § 8](../proto8/thinking/2026-11/03/procs/10-實作時代定-11-03-實作者照原則定的.md#8-收工時改寫成休息中sleepwake11-03-晚)）。使用者「改寫成休息中」「還記得嗎？我們有start/stop, sleep/wake, pause/resume，我們缺了sleep/wake」。照頂層代定做：收工（ctl stop／Ctrl+C／任何走 finish 的退出）時還在跑的 loop 型＝表上 `sleeping`、stack 留著；daemon 再開 adopt 後第一圈用列上的 stack 自動 wake；你 stop 的照舊 `stopped`；收工時暫停中的醒來仍暫停（已實測）；exec 型照舊拿掉；`kill -9` 不在範圍；`aos-daemon-ctl sleep／wake` **先不開放**（原本待他答的 (a)，代定「不開」）、(b) 照建議「醒來仍暫停」。睡著時寄來的 stop＝開門改 stopped 不 wake、rm＝拿掉。
4. **雜項**：
   - WSL `~/repo/simple_tools/aos` 在 `dcca4a8c`，有一個不知誰改的追蹤檔改動 `proto8/lib/aos/ask_round/_tooldef.json`——使用者 11-03 晚「看狀況，隨你」：回公司時看 diff，是工具重產的快取就丟掉再 ff，像有人手改的再問。（11-03 晚 ask_round 整個刪了：ff 前直接丟掉那個改動即可。）
   - Windows 工作樹 `proto8/thinking/README.md`、`months/2026-11.md` 兩檔舊未 commit 改動：使用者 11-03 晚「丟掉」——回公司時 `git checkout -- 那兩檔`（只這兩檔）。
   - 試驗場 `daemons/main` 的 stack 在 `ws/.stack`：使用者 11-03 晚「我以爲daemon本身也可以指定stack？不用移出去」——不移，結案。
   - WSL `~/.codex/config.toml` 預設模型 `gpt-6.1-sol` 這帳號不能用（model_not_found），使用者的設定、沒改。
   - 常駐 bob：使用者「感覺之後會被蛋雕」「先不用管吧」；11-03 晚「B5.封存吧，eca是他的全面強化版，真的沒必要了。」——已結（git 裡只有 thinking，加註；WAIT_USER 那條拿掉）。
   - **11-03 晚開著的事已答並做完**：A2 proc 改名結案（「以後相關的稱呼/慣例等也要變」）；A3 round 的 on_error 緊張「不管」（之後使用者「封存這條線，1.該刪的都刪光刪乾淨」「一起刪……只需要留下他們的概念就好」：`lib/agent/round/`、parts、queue／history／act／compact、`lib/endpoint/`、ask_round、agent-nia、aos-ai〔含 lib/aos 六個工具、Claude skill、`aos_ws.loop_state`〕連程式刪了，概念在 `proto8/archive/agent-round-concepts/`；aos-mcp、aos_ws、aos-say／listen 留著，say／listen 去留頂層另問；NORMS／CONVENTION 只講 round 的條文列在 SESSION-LOG 待收斂）；瘦身候選「先封存，等之後我們進展到那塊的時候可以拉出來看看」→ demo/llm-kernel、demo/self-improve（連 lib/aos/try_run）、nvim 外掛、Lua／Janet agent_dan、aos-chat 進 `proto8/archive/`，環境變數第 4 題結案；`aos_ws.loop_state` 不動：使用者「aos_ws,aos-say/listen,aos-ai這些之後都會整合進aos-agent」（[aos-agent](../proto8/thinking/2026-11/03/aos-agent.md)）；demo/agent-fay 刪（「我沒聽過這東西，刪掉。」），test_fay→test_cli_tools。B4 使用者「等等」。
   - 使用者之後要看 aos-post（impls/aos-post）。
