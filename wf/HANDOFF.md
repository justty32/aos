# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-12 晚 家機頂層收工

1. **授權與工作方式**：在家（家機 Manjaro，`~/repo/simple_tools/aos` main）。頂層只調度，事情交給 agent：普通 opus、雜活 sonnet、規劃 fable；agent 可以再派子 agent；非雜活先讀 wf/ 規矩。**push：睡前（23:15 關機）一次，推之前頂層先跟使用者說一聲**。使用者：「等一下token額度到上限後別動，我有一個免費的額度重置」（頂層轉述）——額度到上限就停在原地等他，不要自己接著做。
2. **今晚新定的規矩**（都在 [tidy content-trim](workflows/tidy/content-trim.md#清舊不必逐項先問2026-11-12-定) 開頭）：「本來就該按照tidy規矩，把舊的東西清掉」＝tidy 判準涵蓋的清舊直接做、事後列清單；「不存在的東西就刪掉。」＝條文講到已不存在的 key／指令／檔／機制直接刪；「還有，什麼11/5幹了啥，這個也刪掉，以後面的爲準，全部匯總成結論，只留結論」＝**條文與說明只寫現在式結論**，之後寫條文的人也照這條（按日紀錄不適用）。
3. **今晚進 main 的**（約 180 個 commit，都沒 push；細節在 [日誌](session_logs/2026-11/2026-11-12.md)）：
   - **外部 MCP**：fsm 經 aos 匯入九步（`15e7f8225`～`b9ca076fc`；新指令 `aos-mcp-import`＋`sync`、`lib/mcp_client.py` 等）；Q1 不做白名單、Q2 stdio server 一律在 server 檔資料夾起（`8c4d73d15`）→ [external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md)
   - **eca**：claude 身開 `Agent`／`Skill`、aos MCP 切主／子兩台（`tools_sub`）`2ab15e1c7`；codex 身只調查 `dc303e087` → [eca-task-subagent](../proto8/thinking/2026-11/12/eca-task-subagent.md)；沒畫面時 `/goal`、`/compact` 失敗不再卡信 `db2018b72`
   - **index 與 `$ref`**：index 每筆可帶 `index`、檔內 `_index` 可為路徑、路徑照 json／檔案系統同像從容器算、收 `#/` 開頭 → [index-link](../proto8/thinking/2026-11/12/index-link.md)；`$ref` 收 `#/`＝寫著它的那份檔 → [ref-hash](../proto8/thinking/2026-11/12/ref-hash.md)
   - **json 工具續行**：aos-json 加 add／ls／search、新工具 `json_len`、`jsonx_multi_get／set`、`json_ls` 的 `depth` → [json-tools 04](../proto8/thinking/2026-11/12/json-tools/04-aos-json下沉與len與jsonx-multi.md)
   - **拆檔與程式碼庫整理**：`aos-eca-turn` 拆成 `aos_eca/`、`cli_session` 拆成八份 `cli_*.py`；fable 領隊整個 proto8 程式整理（行為不變、各批各自 commit，收尾 `ae2fd4e8a`）→ [codebase-cleanup](../proto8/thinking/2026-11/12/codebase-cleanup/README.md)
   - **tidy 三輪**：wf 交接檔瘦身（SESSION-LOG、WAIT_USER 分 `wait-user/`、日誌分月）、conventions 拆檔、C-54／N-28 摺疊、全 docs 沿革只留結論 → [tidy 報告](workflows/tidy/reports/2026-11-12-收尾.md)
   - **thinking→docs 提取**（10-29～11-12）：W1～W7、W9 做完，新條 C-87～C-92、P-47、P-48；W8 等 U1 → [thinking-to-docs](../proto8/thinking/2026-11/12/thinking-to-docs/README.md)
   - **wf→aos**：對標調查（必須的都有、缺的是小輔助）；主 session 的 aos MCP 登記檔修好（repo 外，10 支）→ [wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)、[wf-to-aos 02](../proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md)
   - **試驗場**：家機 11-12 21:04 照 main `415cf6a2c` 第三次整個重建（fsm 48 含 fake_echo、eca 各 26、子 agent 那台 9；假腦／gemma／haiku 子 agent／codex luna／index_view／`$ref #/` 都實跑過；樹停著，`edcb5fc70`）→ [playground-home](../proto8/thinking/2026-11/12/playground-home.md)
4. **使用者今晚的裁定**（原話短引）：
   - 試驗場：「我沒在跑，試驗場那邊也可以全清空。」
   - 全域 MCP：「全域mcp這個我們管不着，只要確定不要干擾到我們的aos就好。」
   - 外部 MCP Q1／Q2：「1.不用，風險自己承擔。2.這個我不是很清楚，如果你覺得要統一那就統一吧，我直覺上感覺OK，反正之後出事再說」；之後「外部MCP，明天再說」（頂層轉述）。
   - index 三題：「1. 甲。2.甲。3.甲，話說ref應該支援#/開頭吧」（都維持現狀；`$ref` 收 `#/` 另做）；index 路徑收 `#/`：「也跟進吧」；資料夾的 `_index.json` 裡寫 `#/` 算不算：「算數。」
   - 拆檔與整理：「東西都弄好後，可以來做重構拆檔+tidy。」「重構拆檔和tidy結束後，派fable領隊，去做整個程式碼庫的整理，架構弄乾淨些。」「盡量做」；tidy 的三句見第 2 點。
   - fsm 真腦跑一晚：「fsm真腦跑一整晚...假日再說。」（頂層轉述）
   - wf→aos 五點：「…4.把人類這個linux user作爲agent，寄信過去就是了。5.對，這個明天開始。」（全句在 [wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)）；「就是說，沒有硬性缺的了，現在wf/的東西，我們拼拼湊湊就能有了。」「以後一定會比wf/好用，放心。寄信這個以後自然就能夠搞定，反正必須的都有了。」
   - 主 session 接 MCP：「好，這些都不是問題。只是主session接mcp這個要處理。邊緣狀況這邊就先這樣，之後踩坑再說。」
5. **下一步**（依優先）：
   1. 主 session 接 aos（明天）：使用者先重連 aos MCP；接著 Skill 放哪、主 session 身分、always-on 規矩、`todo` 歸誰 → [wf-to-aos 02](../proto8/thinking/2026-11/12/wf-to-aos/02-寄信給人與主session.md#明天主-session-開始現在卡在三點)
   2. 外部 MCP 接真的別人寫的 stdio server（明天；要下載先問）＋codex 沙盒對 stdio、`disabled_tools` → [external-mcp 08](../proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md)
   3. thinking→docs W8：等使用者裁 U1 → [thinking-to-docs](../proto8/thinking/2026-11/12/thinking-to-docs/README.md)
   4. 程式碼庫整理剩的（agent-fsm 兩段逐字相同與 `clock_tick`、找 lib 五種寫法、兩處文件舊出處）→ [codebase-cleanup](../proto8/thinking/2026-11/12/codebase-cleanup/README.md#做到哪11-12-晚收線)
   5. 待裁各題（WAIT_USER 01）裁了就照做。
   6. kernel 框架施工與 fsm 真腦跑一晚：假日。
6. **等使用者的**：都在 [WAIT_USER](WAIT_USER.md)（要你裁的、真機驗證、試驗場、雜事四類）；最急的是 push 與重連 aos MCP。
7. **另一台機器（公司）要注意**：pull 之後①重 build 全部 impls（aos-directive 介面變了；aos-json 沒重 build 的話 `json_ls`／`json_search`／`json_add` 會報 `CommandUnknown`）②重跑 `proto8/install.sh`（新指令 `aos-mcp-import`）③試驗場 `lib／py／cmd／templates/agent-fsm` 整份重抄④`~/.cache/aos-mcp-*/tools.json` 的壞格照 [wait-user/04](wait-user/04-雜事.md) 那行指令清。
8. **踩過的坑**：多條線共用一個工作樹時，`git add` 指名路徑後要馬上 commit，不然別人 staged 的會被一起帶走——今晚發生兩次（json 線帶走 tidy 的刪檔、提取 W2 帶走 W5），另有一次誤 amend、已還原；同時開的 agent 數有上限（約 20）；wf-lint 的數字要先看掃描範圍再比。
9. **測試與 HEAD**：已知最近一次全套：`ae2fd4e8a` 時 61 夾 1224 例＋templates 四子夾全綠（出處：程式碼庫整理收尾 commit `ae2fd4e8a` 的訊息）。最終全套與 HEAD：見本條末行（頂層收工時補）。

## 2026-11-12 收工 公司頂層

1. **授權與工作方式**：公司機（Windows＋WSL Ubuntu）。頂層只交流與調度，事情盡量交給 agent（普通 opus、雜活 sonnet、規劃 fable；非雜活先通讀 wf/）。**push：下班前統一推一次**，推之前仍要使用者開口。公司真腦只用 eca（claude haiku、codex `gpt-6-luna`），公司不建 proxy。`/tmp` 殘留與空殼夾准刪（頂層收工處理）。eca「以 CLI 為主、aos 盡量跟上」；「一處壞掉不該擋住其他好的」（工具登記、`_metainfo` 都照這條做）。
2. **main 位置**：WSL `~/repo/aos-tools` 從 origin 的 `8979e1a66` 前進到 `d547d4cf1`（71 個 commit）＋本條收工文書。**push：收工時頂層問過使用者後推；以 origin/main 是否含本條為準**。推了之後家機 `git pull` 就是今天全部；Windows `C:\code\mine\simple_tools\aos` 頂層還原手寫的 HANDOFF 後再 pull。合併做法：各線在自己的 `/tmp/line-*` clone 做、rebase 到 `~/repo/aos-tools` main 再 ff。
3. **今天進 main 的**（原話與裁定都在 [thinking 11-12](../proto8/thinking/2026-11/12/README.md)、[日誌](session_logs/2026-11/2026-11-12.md)）：
   - **工具面**：eca 拿掉 aos 基礎檔案工具，claude 開內建 Read／Write／Edit／Glob／Grep／Bash（dontAsk＋白名單）、codex `workspace-write`（[eca-file-tools](../proto8/thinking/2026-11/12/eca-file-tools.md)）；json 工具全套 `json_*`／`jsonx_*`／`json_multi_*`，`#/` 回標準寫法（[json-tools](../proto8/thinking/2026-11/12/json-tools/README.md)）；knowledge 工具拆除、出廠內容留作普通 json＋index，講已拆機制的內容與條文刪掉（P-46 刪）（[knowledge-removal](../proto8/thinking/2026-11/12/knowledge-removal.md)）；`_index`／`_index.json` 與 `index_view`（[index](../proto8/thinking/2026-11/12/index.md)、[index-tools](../proto8/thinking/2026-11/12/index-tools/README.md)）；`_metainfo`：只活在概念與規範、裡外都認外面贏、壞掉不報錯、`{}` 也算定義（[metainfo](../proto8/thinking/2026-11/12/metainfo/README.md)）。
   - **清帳與小修**：Q01～Q16 一次裁完、agent_def 細改＋lineage、defs 與條文對齊（[small-rulings](../proto8/thinking/2026-11/12/small-rulings.md)、[agent-def-fine-lineage](../proto8/thinking/2026-11/12/agent-def-fine-lineage.md)、[defs-check-align](../proto8/thinking/2026-11/12/defs-check-align.md)）；線 K 收尾與錯誤行不帶絕對路徑（[line-k-leftovers](../proto8/thinking/2026-11/12/line-k-leftovers.md)）；一條工具登記壞掉不拖垮全部＋P-41 改寫（[tool-path-broken](../proto8/thinking/2026-11/12/tool-path-broken.md)）；`aos-agent chat` 打中文不再被丟（[chat-utf8](../proto8/thinking/2026-11/12/chat-utf8.md)）。
   - **kernel**：壞信回 `BodyBad`、fork／subagent 走 `AOS_KERNEL`（[kernel-small-fixes](../proto8/thinking/2026-11/12/kernel-small-fixes.md)）；C-47、N-42、N-63 改寫，猜 `./.stack` 留（[kernel-norms](../proto8/thinking/2026-11/12/kernel-norms.md)）；**通用 kernel 框架圖紙**（fable→Argon 審→fable 改；使用者裁「問腦總機要收進框架」；沒施工）（[kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)）。
   - **eca**：slash 指令 `/clear`／`/compact`／`/status`／`/usage`／`/exit`／`/goal`——畫面同步、say／listen／chat 支援、codex 有畫面、codex `/compact` 撈對話、codex `/goal` 的 Replace 自動選 yes；題 G1、G2 使用者收工前裁「codex目標這塊不用管，就是這樣」＝不做（[eca-slash](../proto8/thinking/2026-11/12/eca-slash.md)）。
   - **外部 MCP**：圖紙、三題照推薦、http＋bearer 試接、施工五步（codex／claude 兩身的 http 與 stdio、新指令 `aos-mcp-launch`、假 server 收進 `proto8/extras/fake-mcp-http`）（[external-mcp 06](../proto8/thinking/2026-11/12/external-mcp/06-施工結果.md)）。
   - **ops-notes 與 Codex agent 進 aos**：盤點完，使用者改成不整套移植、在 WSL 開一塊空間從一個 daemon＋一隻懂 aos 的 eca 慢慢建（原話與照抄步驟在 [ops-notes-to-aos](../proto8/thinking/2026-11/12/ops-notes-to-aos.md)）。
   - **只實測／只記錄**：auto save（`/tmp` 不是記憶體也不快、放 `~/`；使用者裁不做 auto save，停樹後整份複製、頂層建議 `cp -a`）（[autosave § 使用者裁定](../proto8/thinking/2026-11/12/autosave.md#使用者裁定11-12-下午)）；wf/ 往 aos 體系走（只記原話，他要先玩）（[wf-to-aos](../proto8/thinking/2026-11/12/wf-to-aos.md)）。
4. **試驗場**（公司 `~/code/playground`）：12:45 照 main `a85603894` 乾淨重刷＋`eca_opus`、花費無上限（[playground](../proto8/thinking/2026-11/12/playground.md)）。**之後 main 的變更還沒刷進去**：eca slash、codex 畫面、外部 MCP、tool-path-broken 以外的（指令類是 symlink、即時生效）。
5. **下一步**（依優先）：
   1. 外部 MCP 續行（照 06 與 07；07 題一已裁 a 只收 Bearer、F1～F12 使用者「先這樣」）：fsm 經 aos 匯入成包（`aos-mcp-import`、aos-mcp 當 client）；沒驗的 codex 沙盒對 stdio、`disabled_tools`、真的別人寫的 stdio server（要下載、先問）→ [06](../proto8/thinking/2026-11/12/external-mcp/06-施工結果.md)。使用者「做不完就push上去，我回家繼續做」。
   2. 在 WSL 開一塊空間、從一個 daemon＋一隻懂 aos 的 eca（opus）開始慢慢建，使用者自己照步驟做 → [ops-notes-to-aos § 從零搭一棵小樹](../proto8/thinking/2026-11/12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)；搬兩隻 Codex agent（照 06 的照抄步驟、真 token）變成之後的事，盤點與準備步驟也在同一份。
   3. 試驗場重刷（兩台；家機要整個重抄）。
   4. kernel 框架：使用者「kernel先這樣就好，開工等假日。我自己也要思考一下」（[kernel-framework § 已裁](../proto8/thinking/2026-11/12/kernel-framework/README.md#已裁問腦總機收進框架)）；待他看兩處——問腦怎麼收（K-F47 推薦 Python 重寫、刪 C++）、N-63 衝突（K-F50）→ [kernel-framework](../proto8/thinking/2026-11/12/kernel-framework/README.md)。
   5. 外部 MCP 留題：`--envs` 明文落地（05 的 P1，只做了文件警告）、外部 server 壞了 aos 看不到（P3）；代定 E1～E7 待使用者看；外部 MCP 沒經 Argon 審。
   6. json 工具續行點（aos-json 的 add／ls／search、json_len、複雜組 multi）→ [json-tools 03](../proto8/thinking/2026-11/12/json-tools/03-multi與複雜組補齊.md)；index 未定三題（路徑相對誰、過時、專屬工具）→ [index](../proto8/thinking/2026-11/12/index.md)。
   7. wf→aos：等使用者玩完再說。
6. **等使用者的**（都在 [WAIT_USER](WAIT_USER.md)）：要不要 push；真 token 起第一隻 Codex agent；kernel 框架兩處；外部 MCP 代定 E1～E7；試驗場親手玩；fsm 真腦回家測。
7. **家機要注意**：重跑 `proto8/install.sh`（新指令 `aos-mcp-launch`）；C++ 有改要重 build（aos-daemon、aos-json）；試驗場整個重抄；家機兩項殘留准刪、家機 session 動手；`~/.cache/aos-mcp-aos/tools.json` 刪 knowledge／memory 兩格（WAIT_USER 有照抄一行）。
8. **踩過的坑**：scratchpad 多 session 共用、暫存腳本檔名要加前綴（今天撞過一次）；從 Windows 改 WSL 檔會掉執行位元；`wsl … bash -lc '…'` 裡的 `$變數` 會被外層吃掉，複雜指令寫成腳本檔再 `tr -d '\r' < 檔 | bash`。
9. **已知紅**：aos-agent `test_daemon_down` 2 支、box_check 2 支（15:07 在 `3befa7edf` 全套 72 夾 1019 支只紅這 4 支）。最終全套：16:05～16:27 在 `~/repo/aos-tools` 重跑全套（起跑時 HEAD d547d4cf1；期間只合入文件類 commit 至 416fc47d4）：72 夾、1040 支，只紅既有 4 支（aos-agent `test_daemon_down` 的 test_add、test_stop；box_check 2 支），無逾時、無偶發。輸出在公司 WSL `/tmp/fulltest_1112b/`（收工會清）。
