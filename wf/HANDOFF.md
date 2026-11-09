# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-09 晚 收工（家機 Manjaro）

1. **授權與狀態**：使用者在家、本 session 隨意 push；子 agent 普通派 opus、雜活派 sonnet，派前讀 wf 規矩。使用者累了、已收工。家機已跟上 11-09（impls 重建、install、試驗場改成只有根帶鐘，假腦自動驗過，`3670feaaa`）。
2. **設計**：使用者開始**親手大修**，起點 repo 根 [`impl_cpp/`](../impl_cpp/README.md)：骨架取自 `archive/aos-v1`、C++23（使用者先說 20、看到 v1 後改 23）、vcpkg（nlohmann-json、catch2）、Ninja preset debug／release／asan、`.vscode`；第一個零件 `core/inst` 照使用者「aos-inst 也從 aos-v1 拿」原封搬 v1 的 exec＋wire Inst 解析，跟現行 proto8 aos-inst 的差異攤在 `impl_cpp/core/inst/差異.md`，**補不補等使用者**。主角是使用者：agent 只搭環境、照吩咐搬，不替他寫核心。大修材料在家機桌面 `~/Desktop/aos-大修材料/`，第四批後 `proto8/` 沒改、免同步。
3. **新定條號與在跑的 agent**：無新條號；子 agent 都收了。

## 2026-11-09 收工（公司 WSL）

1. **授權與狀態**：使用者在公司、今天通通允許 push、全機 agent CLI 最多 3 個；17:00 下班，已收工、兩份 clone（Windows `C:\code\mine\simple_toolsos`、WSL `~/repo/aos-tools`）同步到收工 commit。WSL vcpkg 重裝在 `~/dev/vcpkg`；公司試驗場 `~/code/playground` 已改三層、只有根帶鐘。大修材料在桌面 `aos-大修材料/`、**不進 repo**（使用者之後自己打包 zip）。
2. **設計**：今天已定——clock＋單位 cycle 大改、熱寫檔省寫、state 拆出 `state_flux`（[clock-and-hot-writes](../proto8/thinking/2026-11/09/clock-and-hot-writes/README.md)）；`aos-daemon-ctl poke [--ctl|--mail|--all]` 訊號門鈴、擋 SIGUSR1／2（[daemon-interrupt](../proto8/thinking/2026-11/09/daemon-interrupt/README.md)）；daemon 不認鐘、方案 B（[clock-decouple](../proto8/thinking/2026-11/09/clock-decouple/README.md)）；格式版本轉正＝使用者大修之後、種子 S1／S3／S4 與 `.bad-*` gitignore 已做（[format-versioning](../proto8/thinking/2026-11/09/format-versioning/README.md)）；大修材料不凍結核心、跟著 main。**未定**：poke 等使用者試用（「這些都可以再討論」，socket／搶占／daemon 叫子項沒做）；大修材料問題清單 56 列待裁；kernel／cases／extras 先放著。其餘 open 看 [SESSION-LOG](SESSION-LOG.md)。
3. **新定條號與在跑的 agent**：N-17 加 11-09 poke 例外、N-09 省寫檔原則與 11-09 註、C-48 加註、N-28／N-05 加註、NORMS 附錄 4 持久檔清單；本 session 開的子 agent 都收了；另有大修材料**第四批**（使用者 15:3x「在嘗試多幫我擴充一些東西吧」選的時序圖、骨架偽碼、4 題 why、速查＋FAQ）11-09 已完成（網頁 179 頁；70 流程時序未實跑驗證），寫桌面、不碰 repo。
