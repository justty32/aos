# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-09 收工（公司 WSL）

1. **授權與狀態**：使用者在公司、今天通通允許 push、全機 agent CLI 最多 3 個；17:00 下班，已收工、兩份 clone（Windows `C:\code\mine\simple_toolsos`、WSL `~/repo/aos-tools`）同步到收工 commit。WSL vcpkg 重裝在 `~/dev/vcpkg`；公司試驗場 `~/code/playground` 已改三層、只有根帶鐘。大修材料在桌面 `aos-大修材料/`、**不進 repo**（使用者之後自己打包 zip）。
2. **設計**：今天已定——clock＋單位 cycle 大改、熱寫檔省寫、state 拆出 `state_flux`（[clock-and-hot-writes](../proto8/thinking/2026-11/09/clock-and-hot-writes/README.md)）；`aos-daemon-ctl poke [--ctl|--mail|--all]` 訊號門鈴、擋 SIGUSR1／2（[daemon-interrupt](../proto8/thinking/2026-11/09/daemon-interrupt/README.md)）；daemon 不認鐘、方案 B（[clock-decouple](../proto8/thinking/2026-11/09/clock-decouple/README.md)）；格式版本轉正＝使用者大修之後、種子 S1／S3／S4 與 `.bad-*` gitignore 已做（[format-versioning](../proto8/thinking/2026-11/09/format-versioning/README.md)）；大修材料不凍結核心、跟著 main。**未定**：poke 等使用者試用（「這些都可以再討論」，socket／搶占／daemon 叫子項沒做）；大修材料問題清單 56 列待裁；kernel／cases／extras 先放著。其餘 open 看 [SESSION-LOG](SESSION-LOG.md)。
3. **新定條號與在跑的 agent**：N-17 加 11-09 poke 例外、N-09 省寫檔原則與 11-09 註、C-48 加註、N-28／N-05 加註、NORMS 附錄 4 持久檔清單；本 session 開的子 agent 都收了；另有大修材料**第四批**（使用者 15:3x「在嘗試多幫我擴充一些東西吧」選的時序圖、骨架偽碼、4 題 why、速查＋FAQ）11-09 已完成（網頁 179 頁；70 流程時序未實跑驗證），寫桌面、不碰 repo。

## 2026-11-08 晚 19:50 家機頂層（20:00 起美國高峰，停止推進）

1. **授權與狀態**：今天隨意 push。使用者在電腦前；**20:00 起不推進**，只整理狀況與回答（原話「八點過後就不用繼續推進了，改成讓我了解狀況與進度」）。arcagi 主 session（tmux `arcagi`，本帳號）19:30 已停手、只答問題。alt 帳號 fable 額度 18:58 用完（22:10 重置），今晚不用。同機 session 傳話雙向寄 wf/inbox（[aos-teams/05](workflows/dispatch/aos-teams/05-同機session與Argon.md)）。
2. **錘子藍圖**：`proto8/thinking/2026-11/08/alt-fable/`。v3 定稿→第二段 out2/（D1～D3、P1、S1、S2 各附 -Argon）→ **v4 由 Argon 整合**（`out2/v4-Argon整合.md`，fable 額度用完）。使用者 19:44 看板裁 v4 方向題**五題全 A**（記在 alt-fable README 末段，已寄 arcagi）：H24 改純盲測＋canary 棘輪守門、無菌鎖收繳稅的純 seed AST、前置夾具淨 +1、inbox 干預記 human_prior_bits＋考核鎖信箱、r09 只插 M1～M7、xform 留 r10。
3. **arcagi r09 收（停手）**：錘子活樹 AUC_L 40（不學 32、手寫拆法 48）、H24 1→2 不退、llm 0、evaluation 仍 56；真蠟模三段都沒擬合（LLM 切的步與空樹語言不對齊）＝r10 頭號題。白話進度 `~/repo/arcagi/notes/rounds/r09/05-白話進度.md`、代定 30 條。Argon 審 r09 規劃（四破口）已寄。**待派**：S1 加 arcbatch `forbid`（等價形狀剪枝，r10 用；信在 `wf/inbox/done/20261108T1915-arcagi-REQUEST.md`），下次開工派 S1 隊長。arcagi 重開時把 `Monitor` 加進 `--allowedTools`。
4. **看板新頁**（5789897b1、d8fffc2b7、b73fc314e）：aos 入門／詳解／帶玩三頁（`wf/tools/progress_board/web/guide*.html`，r09 部分照規劃稿寫、標施工中，r09 蓋好要回頭改）；遊樂場 `~/code/playground-arc-play/`（`source env.sh; play reset; play run`）；首頁新分組頂欄、各線一句話、待你裁橘框；fable 的設計頁加 v3、第二段、v4 三張卡。**還沒做**：論壇／設計／輪次頁頂端換新頂欄；看板測試 `test_rounds_collect` 的 fallback css 比對本來就壞。
