# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-12 收工 公司頂層

1. **授權與工作方式**：公司機（Windows＋WSL Ubuntu）。頂層只交流與調度，事情盡量交給 agent（普通 opus、雜活 sonnet、規劃 fable；非雜活先通讀 wf/）。**push：下班前統一推一次**，推之前仍要使用者開口。公司真腦只用 eca（claude haiku、codex `gpt-6-luna`），公司不建 proxy。`/tmp` 殘留與空殼夾准刪（頂層收工處理）。eca「以 CLI 為主、aos 盡量跟上」；「一處壞掉不該擋住其他好的」（工具登記、`_metainfo` 都照這條做）。
2. **main 位置**：WSL `~/repo/aos-tools` 從 origin 的 `8979e1a66` 前進到 `d547d4cf1`（71 個 commit）＋本條收工文書。**push：收工時頂層問過使用者後推；以 origin/main 是否含本條為準**。推了之後家機 `git pull` 就是今天全部；Windows `C:\code\mine\simple_tools\aos` 頂層還原手寫的 HANDOFF 後再 pull。合併做法：各線在自己的 `/tmp/line-*` clone 做、rebase 到 `~/repo/aos-tools` main 再 ff。
3. **今天進 main 的**（原話與裁定都在 [thinking 11-12](../proto8/thinking/2026-11/12/README.md)、[日誌](session_logs/2026-11/2026-11-12.md)）：
   - **工具面**：eca 拿掉 aos 基礎檔案工具，claude 開內建 Read／Write／Edit／Glob／Grep／Bash（dontAsk＋白名單）、codex `workspace-write`（[eca-file-tools](../proto8/thinking/2026-11/12/eca-file-tools.md)）；json 工具全套 `json_*`／`jsonx_*`／`json_multi_*`，`#/` 回標準寫法（[json-tools](../proto8/thinking/2026-11/12/json-tools/README.md)）；knowledge 工具拆除、出廠內容留作普通 json＋index，講已拆機制的內容與條文刪掉（P-46 刪）（[knowledge-removal](../proto8/thinking/2026-11/12/knowledge-removal.md)）；`_index`／`_index.json` 與 `index_view`（[index](../proto8/thinking/2026-11/12/index.md)、[index-tools](../proto8/thinking/2026-11/12/index-tools/README.md)）；`_metainfo`：只活在概念與規範、裡外都認外面贏、壞掉不報錯、`{}` 也算定義（[metainfo](../proto8/thinking/2026-11/12/metainfo/README.md)）。
   - **清帳與小修**：Q01～Q16 一次裁完、agent_def 細改＋lineage、defs 與條文對齊（[small-rulings](../proto8/thinking/2026-11/12/small-rulings.md)、[agent-def-fine-lineage](../proto8/thinking/2026-11/12/agent-def-fine-lineage.md)、[defs-check-align](../proto8/thinking/2026-11/12/defs-check-align.md)）；線 K 收尾與錯誤行不帶絕對路徑（[line-k-leftovers](../proto8/thinking/2026-11/12/line-k-leftovers.md)）；一條工具登記壞掉不拖垮全部＋P-41 改寫（[tool-path-broken](../proto8/thinking/2026-11/12/tool-path-broken.md)）；`aos-agent chat` 打中文不再被丟（[chat-utf8](../proto8/thinking/2026-11/12/chat-utf8.md)）。
   - **kernel**：壞信回 `BodyBad`、fork／subagent 走 `AOS_KERNEL`（[kernel-small-fixes](../proto8/thinking/2026-11/12/kernel-small-fixes.md)）；C-47、N-42、N-63 改寫，猜 `./.stack` 留（[kernel-norms](../proto8/thinking/2026-11/12/kernel-norms.md)）；**通用 kernel 框架圖紙**（fable→Argon 審→fable 改；使用者裁「問腦總機要收進框架」；沒施工）（[kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)）。
   - **eca**：slash 指令 `/clear`／`/compact`／`/status`／`/usage`／`/exit`／`/goal`——畫面同步、say／listen／chat 支援、codex 有畫面、codex `/compact` 撈對話、codex `/goal` 的 Replace 自動選 yes；題 G1、G2 使用者收工前裁「codex目標這塊不用管，就是這樣」＝不做（[eca-slash](../proto8/thinking/2026-11/12/eca-slash.md)）。
   - **外部 MCP**：圖紙、三題照推薦、http＋bearer 試接、施工五步（codex／claude 兩身的 http 與 stdio、新指令 `aos-mcp-launch`、假 server 收進 `proto8/extras/fake-mcp-http`）（[external-mcp 06](../proto8/thinking/2026-11/12/external-mcp/06-施工結果.md)）。
   - **只實測／只記錄**：auto save（`/tmp` 不是記憶體也不快、放 `~/`；使用者裁不做 auto save，停樹後整份複製、頂層建議 `cp -a`）（[autosave § 使用者裁定](../proto8/thinking/2026-11/12/autosave.md#使用者裁定11-12-下午)）；wf/ 往 aos 體系走（只記原話，他要先玩）（[wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)）。
4. **試驗場**（公司 `~/code/playground`）：12:45 照 main `a85603894` 乾淨重刷＋`eca_opus`、花費無上限（[playground](../proto8/thinking/2026-11/12/playground.md)）。**之後 main 的變更還沒刷進去**：eca slash、codex 畫面、外部 MCP、tool-path-broken 以外的（指令類是 symlink、即時生效）。
5. **下一步**（依優先）：
   1. 外部 MCP 續行（照 06 與 07；07 題一已裁 a 只收 Bearer、F1～F12 使用者「先這樣」）：fsm 經 aos 匯入成包（`aos-mcp-import`、aos-mcp 當 client）；沒驗的 codex 沙盒對 stdio、`disabled_tools`、真的別人寫的 stdio server（要下載、先問）→ [06](../proto8/thinking/2026-11/12/external-mcp/06-施工結果.md)。使用者「做不完就push上去，我回家繼續做」。
   2. 使用者拿真 token 照 06「搬一隻現有 Codex agent 進 aos 的照抄步驟」起第一隻；原話、盤點、準備步驟、未定在 [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md)；盤點結論：只需要一台 http MCP、建議先搬兩隻 gpt-*、ops-notes 主 session 暫不搬（權限：動機器先問 vs eca Bash 不問）。
   3. 試驗場重刷（兩台；家機要整個重抄）。
   4. kernel 框架：使用者「kernel先這樣就好，開工等假日。我自己也要思考一下」（[kernel-framework § 已裁](../proto8/thinking/2026-11/12/kernel-framework/README.md#已裁問腦總機收進框架)）；待他看兩處——問腦怎麼收（K-F47 推薦 Python 重寫、刪 C++）、N-63 衝突（K-F50）→ [kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)。
   5. 外部 MCP 留題：`--envs` 明文落地（05 的 P1，只做了文件警告）、外部 server 壞了 aos 看不到（P3）；代定 E1～E7 待使用者看；外部 MCP 沒經 Argon 審。
   6. json 工具續行點（aos-json 的 add／ls／search、json_len、複雜組 multi）→ [json-tools 03](../proto8/thinking/2026-11/12/json-tools/03-multi與複雜組補齊.md)；index 未定三題（路徑相對誰、過時、專屬工具）→ [index](../proto8/thinking/2026-11/12/index.md)。
   7. wf→aos：等使用者玩完再說。
6. **等使用者的**（都在 [WAIT_USER](WAIT_USER.md)）：要不要 push；真 token 起第一隻 Codex agent；kernel 框架兩處；外部 MCP 代定 E1～E7；試驗場親手玩；fsm 真腦回家測。
7. **家機要注意**：重跑 `proto8/install.sh`（新指令 `aos-mcp-launch`）；C++ 有改要重 build（aos-daemon、aos-json）；試驗場整個重抄；家機兩項殘留准刪、家機 session 動手；`~/.cache/aos-mcp-aos/tools.json` 刪 knowledge／memory 兩格（WAIT_USER 有照抄一行）。
8. **踩過的坑**：scratchpad 多 session 共用、暫存腳本檔名要加前綴（今天撞過一次）；從 Windows 改 WSL 檔會掉執行位元；`wsl … bash -lc '…'` 裡的 `$變數` 會被外層吃掉，複雜指令寫成腳本檔再 `tr -d '\r' < 檔 | bash`。
9. **已知紅**：aos-agent `test_daemon_down` 2 支、box_check 2 支（15:07 在 `3befa7edf` 全套 72 夾 1019 支只紅這 4 支）。最終全套：15:07 在 `3befa7edf`：72 夾 1019 支只紅既有 4 支；最終 HEAD 的重跑結果見日誌末行〔頂層補〕。
