# 試玩紀錄（play）

← [notes 索引](../README.md)｜[proto5 README](../../README.md)｜前一輪原型的試玩在 [proto4/notes/play](../../../proto4/notes/play/README.md)

每個段落收線後，開沒看過設計筆記的 agent 只拿 README 當新使用者玩，照五條標準打分（① 容易上手 ② 容易理解 ③ 複雜藏好 ④ 外層簡單但全面 ⑤ 少背）。一輪一列。

| 輪 | 日期 | 玩什麼 | 報告 | 分數（①②③④⑤） |
|---|---|---|---|---|
| r1 | 2026-09-24 | proto5 重架構後全套：daemon→kernel、真 agent 一整圈、故意弄壞、第二個工具 | [astra](2026-09-24-r1-astra.md)、[Opus](2026-09-24-r1-opus.md)、[任務書](2026-09-24-r1-task.md) | astra 3/4/3/4/2、Opus 2/3/4/4/2 |
| r1 修正 | 2026-09-24 | 兩份報告的十條（A 文件＋小程式、B 碰設計）全做：十分鐘上手、check、init --env、stop 等停好、錯誤附路徑、agent stop 不讀 info、last、done/ | [fix-r1](fix-r1.md) | — |
| r2 | 2026-09-24 | fix-r1 之後：照 README 上手、只看規範架兩個 agent 共用 llm cpu、六類故障（含 daemon kill -9 重開）、自製工具 | [astra](2026-09-24-r2-astra.md)、[Opus](2026-09-24-r2-opus.md)、[任務書](2026-09-24-r2-task.md) | astra 4/3/3/4/2、Opus 4/3/3/4/3 |
| r2 修正 | 2026-09-24 | 兩份報告合併的六條全做：日常 CLI 最小版（init／say／status／continue）、daemon 重開提示 boot、check 驗 K 家目錄、小修一包；README 上手改 init＋say --wait | [fix-r2](fix-r2.md) | — |
| r3 | 2026-09-24 | fix-r2 之後：README 含 init／say／status／continue、「早上開機」三個 agent 輪流 say 九句、弄壞五樣（含 llm cpu kill -9、刪 K/requests）、自製工具 | [astra](2026-09-24-r3-astra.md)、[Opus](2026-09-24-r3-opus.md)、[任務書](2026-09-24-r3-task.md) | astra 4/4/3/4/3、Opus 4/4/4/4/3 |
| r3 修正 | 2026-09-24 | 先把 `aos_kernel.py` 拆成五支（行為不變），再做兩份報告合併的五條：`ls`／`status` 第一行 health、status 的 error 改成「這次原因」＋已恢復的舊錯、沒登記的 say 警告與 --wait 立刻退、say -h 例子、README「每天重開機」、規範標頭沿革搬檔尾 | [fix-r3](fix-r3.md) | — |
| r4 | 2026-09-24 | fix-r3 之後，模型改走 LiteLLM deepseek-chat：README 含「每天重開機」、三個 agent 各三句、port 改壞看 status 講「現在」還是「歷史」、llm cpu kill -9、搬走 K/requests、自製工具 | [astra](2026-09-24-r4-astra.md)、[Opus](2026-09-24-r4-opus.md)、[任務書](2026-09-24-r4-task.md) | astra 4/4/4/4/3、Opus 4/4/4/4/3 |
| r4 修正 | 2026-09-24 | 使用者拍板的命令列改版 13 條：三支指令的家一律 `--target`（環境變數 `AOS_DAEMON_HOME`／`AOS_KERNEL_HOME`→目前資料夾）、`AOS_K` 改名、`aos-kernel init --config`／`halt`／`--daemon-target`、`aos-daemon boot`／`halt`、`aos-llm call`、`aos-agent listen`／`pause`、tick 上 flock | [fix-r4](fix-r4.md)、[astra 審查](fix-r4-review-astra.md) | — |
| r5 修正 | 2026-09-24 | r4 兩份報告的共同痛點八條：health 第一行不再樂觀（恢復中／重試中）、continue 兩階段與 `--all`、listen --last 講中間句並附時間、已登記的 start 退 0、`check --probe`、沒登記的 say 講別再說一次與 `--wait` 先看 health、boot 印一行、`init --force`、NotAnAgent 講哪種家 | [fix-r5](fix-r5.md)、[astra 審查](fix-r5-review-astra.md) | — |
| r5 | 2026-09-24 | fix-r5 之後：`--target` 慣例、daemon/kernel boot／halt、`check --probe`、連敗三階段（重試中→連敗暫停→已解除暫停）、`continue --all`、listen 三模式、pause 中 say、llm cpu kill -9、搬走 K/requests、自製工具 | [astra](2026-09-24-r5-astra.md)、[Opus](2026-09-24-r5-opus.md)、[任務書](2026-09-24-r5-task.md) | astra 4/4/4/4/3、Opus 4/4/4/4/3 |
| one-boot | 2026-09-24 | `aos up`／`aos down` 合一開關機之後：只拿 README＋教程 01、02、06 照抄（開機、kernel 跑工作、手寫 agent 家、第二個 kernel 共用 daemon 與故意撞名）、README 五分鐘 agent、daemon 閒時與忙時各 kill -9 再 `aos up` | [Opus](2026-09-24-one-boot-opus.md) | Opus 5/4/4/4/4；七件已修：[one-boot 追加](../2026-09-24-one-boot/README.md#追加試玩七件) |
| team-r1 | 2026-09-24 | 工具大開發時代第一波收尾：只拿 README＋教程 08，建三人團隊、丟一件事、逐行說 `aos-team mail` 每步誰做、門房、score（模型扮的新手只是代理，使用者要自己看一遍） | [Opus](2026-09-24-team-r1-opus.md)、[任務書](2026-09-24-team-r1-task.md) | Opus 4/4/4/3/4 |
| team-r2 | 2026-09-24 | team-r1 修正＋one-boot 之後：同一份任務書，另一個乾淨的 Opus；多試「不要看單子」看領隊回信（模型扮的新手只是代理） | [Opus](2026-09-24-team-r2-opus.md)、[任務書](2026-09-24-team-r1-task.md) | Opus 5/4/4/4/4 |
| wall-r1 | 2026-09-24 | 第二波 B 隊（牆接線）：只拿 README＋教程 08 第 9 節＋wall.md，不開 kernel：三個成員的 `access ls`、手放兩封冒名信讓郵差退件、`team.json` 加 `cmd_ok` 白名單與故意寫錯、「工人偷看領隊人格會怎樣」（模型扮的新手只是代理） | [Opus](2026-09-24-wall-r1-opus.md) | Opus 4/4/3/4/4；照它改的見 [w2b 報告](../2026-09-24-tool-era/w2b/README.md) |
