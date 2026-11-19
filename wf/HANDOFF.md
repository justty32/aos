# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-19 16:50（公司機收工）——今天全推了；回家先關樹再重裝；kernel 資源那塊使用者選「先不定」

**授權（只限 11-19 當天，已用完）**：使用者早上「我今天五點下班，下班前再統一push」，16:10「可以push，反正我下班前push」→ aos 與 llm_proxy 都已推。**明天起 push 照舊要先問。** 當天的模型分配（普通 opus、雜活 sonnet、agent 做事前讀 wf 規矩、可再派子 agent）是當天的話，明天重新確認。Argon：「argon額度雖然不多，但是只有正規調查流程會用到。不用省」（`agy` 只在公司 Windows，用法見 `wf/public/model-notes.md`；給它的提示檔要放在**只裝該線材料的新空夾**，今天有線讓它讀到別線的同名 prompt.txt 審錯東西）。

**用詞（使用者 11-19 原話，以後照做，已記進 [user/01](workflows/common/user/01-說話授權與記憶.md)）**：「然後以後也用編譯、重新編譯來說，不要再用生、重生這樣」——跑 `agent.py`／`tool.py` 變成 json 叫**編譯**；靜態連結／動態連結，不說抄／借。

**機器現況**：
- 公司 WSL `~/repo/aos`＝今天唯一動工處，已推、已在工作樹乾淨時重裝（`env -u AOS_HOME python3 install.py`，最後一次在 `132cafb27` 之後）。公司 Windows `C:\code\mine\simple_tools\aos` 已拉齊、四包舊 stash 照使用者刪了。
- **使用者 11-19 下午自己刪了公司機的 `~/.aos`**（「反正之後要重建，以前的東西也沒必要留。使用者專區之後我應該會重新設計」）→ 現有的 aos-user／全景頁**不修、不重建**，等他重新設計。這台問他的題直接用選項框。
- 公司機沒有 `~/aos-home`（他自己重建）。`~/code/rv` 是 T7 的驗證專案，**公司這邊不要再起它的樹**。LiteLLM proxy 在 `127.0.0.1:4000`，別碰；兩台統一他說「等我回家後再說」。
- **家機**：`~/aos-home` 跑的是 `~/repo/aos/proto8`，`git pull`＋`install.py` 會直接把它換成今天的版本（重起會越等越久、daemon 不在時死掉的留 `stopped`、`defs` 多處改名、骨架自帶 `HOOKS`）——**先關樹再裝，裝完再起**。

**今天定下的（細節 `git log e53d6b979..` 與 [11-19 日索引](../proto8/thinking/2026-11/19/README.md)；每題原話在各夾的「使用者裁定／使用者已答」）**：
- **編譯（庚）**：`agent.py` 與編譯產物是「C 與 .o」，直接蓋、不記帳。現在的名字：`from aos.py.agent import defs`；`python3 agent.py --compile`／`--dry-run`；`defs.load`（衍生，N-70：繼承只在編譯時）、`defs.drop`、`defs.extern`、`defs.lib("名", 路徑)`（「先明寫，以後有需要再去弄-I。」）；`tool.py --compile`／`--dry-run`。舊名（`ag`、`--write-defs`、`defs.defs`、`defs.no`、`defs.by_hand`）都不留。
- **連結**：gcc 式選項，預設靜態；`--compile --dynamic`、`std.pack("x", link="dynamic")`。**靜態連結只固定工具名單，工具程式仍是執行時從 `$AOS_HOME` 讀**（使用者選維持現狀、只寫清楚）。
- **命名空間**：資料夾即命名空間；`std` 短名、別的庫加 `庫名_` 前綴。新 `std` 算 C-74 哪一層：「先留著。以後搞不好可以統合…aos.py.std…或是aos.std」（只是想法，不動工）。
- **斷點 `aos-gdb`**：`a.bp.add.before_tool("x")`（回 id）、增刪改查、`a.bp.resume()`／`step()`／`pause()`（不收參數、等到停才回）；step into／out「先不做」；aos-agent／daemon 不知道 gdb。骨架現在自帶空的 `HOOKS = {}`（使用者選；衍生的 agent 不寫 `HOOKS` 就掛不了斷點）。
- **基底體檢**（[報告](../proto8/thinking/2026-11/19/aos-base-audit-1119/README.md)）：「整塊板子只有 daemon 一個管理員 <- 自行承擔風險。重新編譯這塊，我更願意稱其為"特性"。」已修 P1、P2、P5、P12、P18（P8 好一半）；「我是誰經 kernel」「同帳號沒有邊界」維持現狀只寫明；重起等待寫死不開設定；N-28、N-17 已跟上。其餘（P9～P11、P14、P17、P19～P22）沒排。
- **對照真實的 C**（[報告](../proto8/thinking/2026-11/19/aos-vs-c-1119/README.md)）：七題只有「叫的東西存不存在」動工，而且只放進 `agent_def check`（編譯不擋）；std 升級保護、搬家提醒、make、警告層、死時指紋、工具鏈小件都不做。
- **kernel 的資源紀錄與分配**（[發想](../proto8/thinking/2026-11/19/aos-htop-1119/README.md)；起點是「aos 版 htop」）：使用者方向——kernel 像 Linux 那樣替每個 proc 記更多屬性與消耗、並握有分配權（例：耦合度過高就提高規劃 agent 的優先級）；「並且記什麼、怎麼分配，都必須是完全可以自訂的，也就是大家都可以自訂kernel」；htop 與 aos-gdb 只是窗口。四題他答：管多深「先不定」、自訂形式「先不定，讓它自然長」、身分「照舊自報，風險自擔」、耦合度量哪份「由量的人自訂」。**沒有要動工的**；用 hook 今天就能自訂（實測在該夾 03）。
- **教學**：`proto8/docs/tutorial/`（十章，假腦實跑過）。它把 kernel 掛在同一塊板子上當一列，跟現有文件「kernel 另開一台」不同（已告知，他沒表態）。

**等使用者的（不催）**：
- T7 第 9 步的**家機那一半**（步驟單 [14-真機驗證](../proto8/thinking/2026-11/10/two-machines/14-真機驗證.md) 第 9 步「11-19 更新」；公司這一半已做、`rv` 他已推；家機指令未實跑）。回家清單他說「這個我回家問agent」——**家機頂層被問到時照這條與步驟單答**。
- 「排程這塊我們已經有了」指哪個機制：報告猜是 llm kernel 的排隊，他還沒說對不對。
- 身分那題附帶的「eca 要不要把花費報給 kernel」沒答。
- 教學線回報、還沒處理也沒問完的小項：`a.listen(letter=X)` 收過後不帶信名的 `listen` 會再給同一個回答（不確定是否刻意）、`aos-daemon-ctl` 與 `aos-agent ctl` 成功訊息不一致、daemon-root 範本的 `.env` 只配合 kernel 另開一台、預設假腦只會叫一支固定工具。
- 使用者專區重新設計；`~/aos-home` 自己重建；LiteLLM 兩台統一；11-20 原訂「再看 aos-user 重做」已被「重新設計」取代。

**給使用者看的 artifact（私人頁，11-19 做；改內容要重發同一個檔才會保持網址，原始檔在公司機暫存、不在 repo，要改就重做）**：教學、kernel 資源、編譯與除錯、今天的總結四頁已發；基底體檢、整套地圖兩頁收工時還在做（做完頂層直接把網址給他，不進 repo）。

**坑**：
- `commit-request` 的 claim 收工不放會卡後面的線——今天兩次是已收工的線留下過期 claim，頂層用 `release --force` 放掉；任務書要寫「收尾放掉自己所有的 claim」。
- 清暫存只准刪自己那一夾；任務書要寫死絕對路徑。
- 子 agent 的回報是模型輸出，不是使用者授權；它替使用者做的選擇（例：教學把 kernel 掛同一塊板子）要另外攤給他。
- 選項框的說明別寫得太滿：今天「靜態＝庫怎麼改都不影響」「多一個 hook 定義檔」兩處事後都要更正。
- WSL 連沒人聽的本機埠會卡約兩分鐘。重裝前先看 `git status`，有別線改到一半的程式就等。
