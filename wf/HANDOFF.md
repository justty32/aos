# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-22 收工（公司，WSL）

1. **授權**：本 session 使用者說可隨意 push；git 一律走 WSL（justty32）：`wsl git -C /mnt/c/code/mine/simple_tools/aos ...`；push／pull 加 `-c 'url.git@github.com:.insteadOf=https://github.com/'` 走 SSH；Git Bash 裡跑 wsl 路徑會被改寫，要用 PowerShell；多 agent 時不用 `--autostash`、只 add 自己改的檔。分工：普通工作 opus、簡單雜活 sonnet、fable 只在點名時用；頂層只跟使用者交流。
2. **今天做完**：
   - s6／runit 兩份對照（proto8/notes：85aa65f0、9d62b2c9）、.env 格式比較（714311c1）。
   - 修教學小毛病（485b96e5）。
   - 改寫公司帳號 commit 並強推：新 main 起點 2cd76e2d，[對照表](session_logs/2026-10/2026-10-22-author-rewrite-hashmap.csv)，WSL 備份 `~/backup/aos-2026-10-22.git`；simple_tools gitlink 已更新（7ecd5309）。
   - Python 版 aos-inst 改成庫、`#!` 寬鬆、.env 行首只認 ASCII 空白（73fe3bc9、6130e0bf）。
   - .env 改 dotenv 基礎子集＋`--dotenv-override`（預設不蓋、只管這一跳），`a#b` 照字面，值頭尾 Unicode 空白照 python-dotenv 去，`AOS_*` 規則留（24fba8c1、a9b1d54a）。
   - 分層 C-74（基礎層＝核心 aos-exec＋loop、daemon；標準庫＝fsm、tasks…；最上層 agent／kernel）與三條撞名改名（系統本體、最小／完整實作）（524de69b）。
   - loop 條文定稿，四問題使用者自行承擔（c849afaa）。
   - daemon：重開＝重新開始、子項名字擋 ctl／state 撞名、N-28 未做的拿掉、舊小格 ctl.json 使用者自己刪（5e9cb1a4、fb22adf3、97bc8c4a）。
   - fsm：state 讀不了退 1、開跑查整張表、條文定稿（396d61fd）。
   - gotchas 拆檔、壞連結修（e294d7ad、845e18b9）。
3. **open**：
   - **回家第一件事**：家裡那台 aos `git fetch` + `git reset --hard origin/main`（不要 pull）；simple_tools pull。
   - impls（C++，只在家裡）要跟上 10-22 bin 版：.env 新格式與 `--dotenv-override`、daemon 子項名字檢查、fsm state 讀不了退 1 與開跑查表、USAGE 補 `[旗標]` 等；bin 版錯誤代號照 impls 補齊（細節在 [SESSION-LOG](SESSION-LOG.md) 最新進度）。
   - 方向題仍等使用者：tasks、tool_calls、兩種 kernel（[WAIT_USER](WAIT_USER.md)；s6 報告的 c/d/e 先不討論）。
   - 還是草稿的條文：N-14 窗總則、N-15 鎖、N-16 信箱、N-34 tasks（都沒有實作可對）。
   - 小注意：`aos_llm_tests` 今天一次偶發失敗、重跑過；這台 Windows git 全域 email 是公司帳號（今天都走 WSL 沒影響，改不改由使用者）；repo 的 `stash@{0}` 是 09:10 半截 rebase 留下的 autostash，內容已確認回到工作樹，可由使用者決定要不要 drop。
