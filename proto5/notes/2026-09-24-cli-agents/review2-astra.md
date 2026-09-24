← [本提案](README.md)｜[stage0 報告](stage0.md)｜[任務書](review2-task.md)

# astra 唯讀審查：cli-agents 階 0（2026-09-24）

結論：**範本結構可行，但權限說明、成功判定及清理指令有必修問題。**

本次全程唯讀；未跑模型任務、daemon、LM Studio／ollama。核對本機 Claude Code 2.1.281、Codex 0.156.1 的 help，五份 JSON 解析及腳本 `bash -n` 均通過。stage0 的歷史真跑結果僅核對紀錄，未重新驗證。以下路徑均相對 `proto5/`。

## 必修

1. **`templates/cli-agents/README.md:34–35`、教程 07 第 4 節、stage0 待拍第 4 題 →「不准跑任何指令」不成立。**  
   本機 help 明說 `--permission-prompts none` 只拒絕「原本需要詢問」的動作；內建免確認的唯讀指令仍可執行，`acceptEdits` 還會放行工作目錄內的部分檔案操作指令。建議兩份 Claude 範本加 `--restricted`，保留 `--safe-mode`，且不要用 `--tools` 加回執行工具，再同步修改說明。這符合已定的保守方向。[Claude 官方權限說明](https://code.claude.com/docs/en/permissions)

2. **同上「加 `Bash(make test)` 就能安全跑測試」→ 授權比表面寬。**  
   Claude 能改工作區內的 Makefile，再執行被允許的 `make test`；測試配方可執行任意程式，外層的 git push 拒絕規則不會逐一審查其子程式。建議刪掉把它當安全白名單的說法，明寫「允許執行工作區程式，須信任測試內容；牢外不保證只改工作區」。

3. **`notes/2026-09-24-cli-agents/stage0-run.sh:72–85`、教程第 5 節 → 沒落實「上一次成功的」。**  
   腳本沒保存、檢查 kernel 回音，只用 `d.get('is_error')` 判斷；欄位缺失也被當成功。輸出已寫好但隨後逾時／被停的任務，也可能被拿來分岔。c2 成功後，`last-ok-session` 仍留 c1。建議先確認回音無 error、`kind=child`、`code=0`、`timed_out=false`、`stopped=false`，再要求 Claude `is_error is False`、`subtype=success`；兩層通過才更新 id。教程及成功表一併補齊。

4. **`stage0-run.sh:7、33–66` → 前面失敗，後面仍繼續花額度。**  
   只有 `set -u`；初始化、boot、登入連結、投遞或等待失敗都不會可靠中止。Codex 失敗後，`--with-claude` 仍可繼續送單，整支腳本也可能退 0。建議逐步檢查回傳值及工作回音，失敗即停止後續投遞，以非零結束；EXIT 清理保留原失敗碼。只加 `set -e` 不夠，因 `add` 收到失敗工作的 result 仍可退 0。

5. **教程「收工」末行 → 刪掉共用 `$W/jobs`，會波及教程 02 等既有工作。**  
   07 沿用 01 的 `$W`，這個目錄不是本篇專用。建議本篇改用 `$W/cli-jobs/`，清理只列本篇建立的目錄；確認相關 cpu 已停後再刪。`halt` 報 Timeout 時不可接著清空仍在使用的家。

6. **所有 `sed` 換字處、腳本接受的 `[W]` → 合法路徑可能被換壞。**  
   唯讀測試確認：路徑含 `&` 會留下 `@WS@`；含 `"` 會產生非法 JSON；含 `|` 會讓 sed 出錯。空白路徑另會破壞教程未加引號的參數及腳本 `awk '{print $2}'`。建議用 JSON 解析後替換字串再序列化，shell 路徑全部加引號；回音路徑用單名與 K2 組合，別用空白切路徑。或明確限制並驗證允許的路徑字元。

7. **教程「三個洞」第 3 條、第 6 節 → 把取消保證說得太滿。**  
   daemon 的 kill 回音是**立即受理**，不是死透證明。預設 5 秒後是 TERM，必要時再等才 KILL；`cpu/stop.md` 明定脫離 process group 的後代不保證收掉，stage0 自己也記了此風險。建議改成「嘗試停止 cpu 與工作程序組；確認舊程序退出，另查脫離組的後代」。並說清楚 `Removed` 是原 **add 單**的回音，rm 自己成功回的是名稱。

## 建議

1. **教程前提與第 1、3 節 → 少了目前目錄條件。**  
   `. env.sh` 不會切回 repo；新終端照做時，`$PWD/proto5` 可能不存在。補上「先回 repo 根目錄」，或明確設定 `R`，後續用 `$R`。

2. **`kernel2.json`／教程第 1、2 節 → 補清環境的適用前提。**  
   `$env` 讀 daemon 原環境，`clear` 不會先把它清掉，這部分正確；但代理、憑證路徑等也會被移除。建議提醒依賴這些環境的安裝須逐項補回，登入前提也應明寫 `~/.codex/auth.json` 必須存在。k2 本身沒有 clear，文字應限定為三顆工作 cpu。

3. **教程登入段 → 把 stage0 已記錄的符號連結風險帶過來。**  
   原子替換登入檔可能使連結變普通檔，不能保證永久同步；專用 `CODEX_HOME` 也不等於全面停用其他設定來源。建議說清楚只隔開原本的使用者家；專案及系統設定仍需另看。[OpenAI 官方設定層級](https://learn.chatgpt.com/docs/config-file/config-basic)

4. **stage0「五條驗證」、導航新增列 → 區分已驗與未驗。**  
   第 5 條是依指示跳過；額度耗盡、無 fork 的 resume、完整後代清理也未驗。導航「五條真跑驗證」宜改「四項實測紀錄＋牢測試跳過」。教程「都很小」也宜改成只描述任務數量：報告中的 Codex 審查已有約 139k input tokens，不能拿題目短當額度很小的保證。

## 確認沒問題的

- 普通 cpu 池、另一個 K2、Claude 1 顆／Codex 2 顆及唯一 cpu 名稱，符合既定方向。
- 五份 JSON 合法；inst 路徑、`mkdir`／`append` 選項及 daemon 環境中的 `$env` 用法符合規範。
- 四份工作 argv 沒啟用跳過權限旗標；Codex 均指定 `gpt-6-astra`。
- Claude 的變長 `--disallowedTools` 放在 argv 最後，提示走 stdin，目前不會吞掉後續 session 或提示參數。
- Codex 的 `-s`、`-C` 放在 `fork` 前，與本機 help 的命令結構一致。
- kill／ack 信封、ack 檔名前綴及 `.tmp → ln` 投遞格式正確。
- 「池只限制同時數量」「另一個家不是權限隔離」「rm 不停止正在執行的工作」三個核心提醒正確。