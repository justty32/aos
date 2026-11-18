# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 晚（家機）——關機打斷的五條線已分件：兩條交了、三條程式寫完但沒做完，留在工作樹

**先看這個**：公司機 17:00 關機留下的總補丁（`proto8/thinking/2026-11/18/交接-各線/工作樹未交改動-1118.patch`）家機已套進工作樹、照各線交接分件。**main 現在裝得起來**（關機前那兩筆交接 commit 把 aos-kit、aos-tree-start 的刪除誤帶進去、`py/entries.json` 還列著它們，`install.py` 報 EntriesBad；已修）。已交（都沒 push）：
- `dc4218e8a` 修補：aos-kit 本體與測試 19 檔從 7deb30b3c 前一版拿回（kit-merge 沒做完，先回到能裝）、entries.json 拿掉 aos-tree-start、`wf/tools/codemap_lib.py` 的檔頭判讀不再把「pi coding agent」當編碼宣告跳過（這個讓 index_gen 報 DescMissing cli_pi.py、commit-request 一件都交不進）。
- `93e0acc0c` rm-treestart-1118 做完。
- `2b4320644` cooldown-1118 做完（件 A 冷卻檔多 retry／error 兩欄；件 B 三小修）。
- 這筆之後的收尾 commit：本檔、`wf/progress.json`、三條未完線的補丁、日索引補 aos-llm 調查那列。

**三條沒做完的**（程式寫完、在家機暫存複本全套測試都過，但各自的文件／收尾沒做，照「不硬補」沒交）：改動**留在工作樹**，另各存一份補丁在交接夾 `<線名>-未交.patch`（對 `2b4320644` 之後的 main，乾淨 clone 上 `git apply` 套得上）。工作樹跟補丁只差一處：kit-merge 要刪的 aos-kit 19 檔在工作樹裡還在（修補拿回的；不刪檔）。
1. `kit-merge-1118`：剩設計稿 `18/aos-kit-併進ctl.md`（程式檔頭與 README 已先連過去）、試驗 08 與教學目錄 08 列各加一句、裁定逐字記進 `cpp-py-改名/08-要裁的題.md`、日索引、假腦實操、最後 `grep -rn aos-kit`；交時連同 aos-kit 19 檔刪除一起交。
2. `eca-pi-bc-1118`：剩文件 `templates/docs/03-eca-pi.md`（還是甲案）、knowledge `cli/eca.json` 的 `#/pi`、`apps/eca/README.md` 第 12 行；真 pi 整樹實跑（`pi_aos_screen.mjs` 沒在真 pi 上跑過）；已知限制要寫。
3. `eca-lab-1118`：15、16、18 寫完；13、14、17、19 要重派（18 連到 17 的連結現在是斷的）；README「共同準備」與 01～03 內文還寫 `aos-tree-start`。

**測試（家機，`~/.aos/scratch/home-1118b/`，乾淨複本各自 install.py）**：改前（HEAD＋拿回兩支）2760 支、交的兩線 2766 支、五條全上 2766 支（kit +8、pi +10、aos-kit 舊測試 20 支拿掉）。三份唯一的紅都跟這五條無關：`image-move-check` 等 worker 逾時（CheckFailed）每份都紅；`cpp/aos-loop` 的 `test_cause_sigint_ignores_file` 在兩份並行跑時紅、單跑那份綠（負載下不穩）。另外 `py/tests` 有支測試會留下 `/tmp/kernel-state-path-*` 的 daemon（家機跑舊 HEAD 時抓到一隻，已用它自己的 stack shutdown）。

**要使用者裁的**（各線交接檔有原文）：cooldown——listen 的字少了 `aos-llm: error:` 前綴、SendFailed 少了 aos-llm 原話可不可以；關畫面順手清到期單要不要只限 set-def。rm-treestart——跳過 `source env.sh` 直接打 `aos-exec root` 沒人擋（甲不補／乙補在 daemon-root 範本／丙補在 aos-exec）。kit-merge——寫進 stack（現做法）還是像舊 aos-kit 改定義夾；eca 定義要不要也能套；換包要不要允許直接蓋。另：`proto8/templates/tests/kits/_index.json`（使用者自己放的，生成器不產它、commit-request 也不收）還是沒進 git 的檔；`proto8/impls/` 底下 12 個舊 `.a`／`.so`（改名前的建置產物，現在沒人管）也沒動。

**授權**：頂層只調度（普通工作 opus、雜活 sonnet、規劃 fable），agent 開工前讀 AGENTS.md、規矩卡、`proto8/knowledge/aos/_description.json`。push 要再問（頂層說今晚 23:00 一次 push）。前端先不動。家機本地 main 原本超前 origin 那一筆 `abed65ecd`（SESSION-LOG 記 11-16 晚 Pages 剩項）沒 rebase，改寫成 progress.json 的 `pages-trial-1116`；原 commit 留了 tag `home-local-abed65ecd-1118`。

**今天已交已推的重點**（細節看 `git log --since=2026-11-18`）：S3～S7 改名收尾、code map 依賴表、沙箱帶整個家且家先認 `AOS_HOME`、set-def 新做法與 `ctl stop` 延後關、收尾線四項裁定、清紅測試（36→0，缺環境的改跳過）、`stop_cause.json` 不進 git、listen／ask 出錯帶理由、eca 第三種身 pi 甲案、小試驗教學 01～12、沙箱隔離實機檢查、下午改動獨立驗證、litellm 說明、aos-llm 去留調查。

**使用者已裁、還沒做的**：
- `aos-llm` 走丁案（Python 函式庫 `py/aos/llm_client.py`＋同名薄指令；推翻 11-17 X-4 A 的 `llm` 那一半）——使用者：「丁，明天再做」「也有可能往後延」。**要做之前先問他。**
- 真模型端點：等他把家裡的 litellm proxy 帶來公司（「等我回家把那個推回來公司再說吧，要等明天了」）；公司 `~/litellm-proxy/`（1.109.1）留著沒起、沒登入。之後接著做：API 真模型試跑、沙箱裡 agent 跑真模型、重建試跑紀錄補真 API 一節。
- pi：用他自己裝的那份（`~/.local/bin/pi`，1.5.2，已登入 ChatGPT），不釘版；`context_wrap` 在 pi 身先不開、靠 pi 自動壓縮（「這個得再去想想辦法」）；重建樹時 `env.sh` 要加 `export PATH="$HOME/.nvm/versions/node/v24.19.0/bin:$HOME/.local/bin:$PATH"`；家機要他自己換新版 pi。
- 預設 stack（cd 到 agent 夾直接 say）：他「得再想想…之後再來規劃」。
- 試驗抓到的問題「都還好…剩下的都不用管」；絕對路徑 `ctl add` 記成相對路徑那個他自己試。

**還沒問／沒裁的**：沙箱實機檢查的落差（起手範本擺法讓沙箱碰得到 daemon 的 stack〔嚴重〕、開網路的沙箱連得到宿主本機服務、WSL 的 DNS 要綁 `/mnt/wsl/resolv.conf`）；litellm 版本要不要退 `1.106.x`、要不要長駐；hook_run 把 aos-directive 錯誤行照轉 stderr 要不要改回；`--restart` 已拿掉與沙箱兩個代定細節他沒反對。

**機器狀態**：公司 WSL 沒有 aos（等使用者另開 session 照 `proto8/thinking/2026-11/18/公司WSL-重建試跑紀錄.md` 重建）。`~/.aos/scratch/` 有今天各線的暫存（關機後行程都沒了，夾還在）。桌面 `aos-全景-1118` 沒人眼看過。家機重建沒做；家機這輪的測試複本與腳本在 `~/.aos/scratch/home-1118b/`（`tests.sh <夾名>` 跑全套、`logs-<夾名>/summary.txt`），行程都收了。
