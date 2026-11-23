wf/advices 入口：AI 對 aos 本身的意見精簡版的導航、怎麼投新意見，以及舊打撈包、實驗、調查留下還有用的幾條結論。

# wf/advices — 對 aos 本身的意見

← [WORKFLOWS](../WORKFLOWS.md)

各隊做事時對 **aos 本身**（daemon、信件、kernel、fsm、工具、指令、知識庫、文件）冒出的改進意見。要改進 aos，先從這裡找參考。由頂層管理。跟 [wf/public](../public/README.md) 的分別：public 收「怎麼用 aos 做事」，advices 收「aos 哪裡該改」。

使用者 11-14：「然後大家做一做，會有一些對於aos的意見，也請你收下，並另外派claude subagent整理，並放入wf/advices，之後有要改進aos，我們就可以從中找到參考」

使用者 11-17：「wf/advices是蒐集AI對aos的意見，可以封存，只提取精簡。salvage,digest,experiments,investigations通通封存，只提取精簡後的一點點東西，放到wf/advices。精簡後的東西，wf/advices希望只剩下兩三個小於8kb的檔案。」

## 有什麼

本夾頂層只放這三個檔，每個小於 8 KB（子夾 `feedback/` 是 aos-feedback 的資料）。每條一兩句，括號是出處。做掉一條就刪那條。原本 99 條的全文與各批整理紀錄 11-17 隨各 archive 刪掉了（看 git 歷史）；`archive/` 現在只放 11-17 從頂層搬來的 salvage（這夾 11-17 也刪了，見 git 歷史 b01a893de）。

| 檔 | 收什麼 |
|---|---|
| [01-daemon信件kernel安全](01-daemon信件kernel安全.md) | 安全、daemon 與行程、kernel 與額度、信件與溝通 |
| [02-範本工具知識庫](02-範本工具知識庫.md) | agent-fsm 與 sol、eca 範本、commit-request、工具說明、知識庫 |
| 本檔下半 | 舊打撈包、實驗、調查留下的坑與未解問題 |

agent 用 `aos-feedback add` 送的單筆指令意見在子夾 [feedback/](feedback/README.md)（程式預設的存放處，11-17 從 `proto8/feedback/` 搬來），看法是 `aos-feedback ls`、`show KEY`。

## 投新意見

1. 隊伍把稿放在自己工作區 `wf/temp/<線名>/aos-advice/<題目>.md`，一個意見一份：哪裡、現象（附指令與輸出）、建議、痛的程度（擋路／拖慢／小不便）、出處。不 commit、不自己改 wf/advices。
2. 寄信給 xiaosi，title 開頭寫 `[aos-advice]`，what 列稿的路徑；xiaosi 轉給頂層。
3. 頂層派 Claude 子 agent 整理：查秘密與私人資訊；查 repo 是不是已經改好，改好的不收；同一件事合成一條；照上面的寫法加進對應的檔。檔要超過 8 KB 時，先刪已做掉的，再合併。
4. 頂層走 commit-request 交件。

## 舊包留下的坑與未解問題

出處：salvage＝`wf/salvage/archive/`，experiments＝`wf/workflows/experiments/archive/`，investigations＝`wf/workflows/investigations/archive/`。

- Claude 訂閱只有官方 Claude Code CLI 與 claude.ai 能用。aos 要拿 Claude 當腦，只走 eca 叫官方 CLI，或用 Console 的 API key；不把訂閱的 OAuth token 接進 kernel_llm、不寫帶 Claude Code 身分標頭的客戶端、不做把 CLI 包起來對外開 API 的 proxy。條款是 2026-09-13 查的，之後沒再查。（experiments `claude-subscription/README.md`、`claude-subscription/web-findings/01-litellm-與官方態度.md`）
- 改信箱、認領、鎖、claim 這類靠 rename 的檔案協定，要跑併發壓力（K 支同時跑幾百次，量重複率與遺失率），修掉一個 bug 後重量一次：舊分支修完一個去重 bug，重複執行率從 9.8% 升到 37%，當時 ctest 全綠。（salvage `02-踩過的坑.md` 第一節、`06-協作流程的收穫.md`）
- rename 會靜默蓋掉目的檔，原子但不互斥；要互斥用 link、RENAME_NOREPLACE 或 O_EXCL。隔離、歸檔走 rename 時，同名第二份會蓋掉第一份證據。部分成功（link 成了、收尾 unlink 失敗）要回成功、殘留另報，不然生產者重投就多一份。其他檔案型的 rename 沒逐一查。（salvage `02-踩過的坑.md` 第四、五、七節）
- 讀別人寫得進去的資料夾前，先驗是普通檔：放一根 FIFO，open 就永遠卡住。兩層程式別用不同 syscall 判斷檔在不在（斷掉的 symlink 對 lstat 在、對 open 不在）。aos-post 的 take 有沒有驗型別，沒查證。（salvage `02-踩過的坑.md` 第二節）
- 時序測試不用 sleep 佈置，讓被跑的那格自己在執行中做那件事；測「不該永久卡住」的案子自帶 alarm／timeout 看門狗。（salvage `05-程式碼哪些值得抄.md` 第七節）
- daemon 的 auto_restart 只在「連 3 次都在起來 3 秒內就退」時停，一個每次跑 4 秒才失敗的 proc 會被無限次全速重起：停下的判準要看有沒有進展。程式沒看，沒查證。（salvage `02-踩過的坑.md` 第六節）
- 記裁決時把反面代價一起記，問一句「它還會把什麼當成相同、當成不同」；一個 bug 意外提供的保護是巧合，不是設計。（salvage `06-協作流程的收穫.md`、`03-裁決與其理由.md`）
- 條文只釘已經站穩的行為：先做出會跑的最短路徑再寫規格；計畫只寫到下一步能不能開始。使用者原話：「像這樣一改再改，實在浪費 token，不如全部打掉重來，這才是 agent 的正確方法。」（salvage `06-協作流程的收穫.md`）
- 未解：daemon 若用宿主 root，或做 subuid 第 3 段，只留 CAP_SETUID／SETGID 仍可冒用宿主登入使用者，外牆要從 daemon 外面加（systemd 限制、AppArmor、Landlock 或 userns 配 subuid），也不能留請牆外代辦的通道（systemd bus、docker socket）。調查建議「防線不在就拒絕啟動」，跟使用者 11-12 對 aos-sandbox 的裁定（設定壞了就當沒寫、直接跑）方向相反，做之前要問。（investigations `proto5-host-root-second-wall.md`、`proto5-linux-wall-feasibility.md`）
