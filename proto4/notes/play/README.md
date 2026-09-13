# 試玩紀錄（play）

← [筆記索引](../2026-09-08-ideas.md)｜規則在 [§21.5](../20-21-step-lisp-and-next.md)

每個段落收線後，開沒看過設計筆記的 agent 只拿 README 當新使用者玩，照五條標準打分（① 容易上手 ② 容易理解 ③ 複雜藏好 ④ 外層簡單但全面 ⑤ 少背）。一輪一列。

| 輪 | 日期 | 玩什麼 | 報告 | 分數（①②③④⑤） |
|---|---|---|---|---|
| r1 | 2026-09-13 | proto4-3（OS 層）＋ proto4-4（逐步 lisp） | [Opus](2026-09-13-r1-opus.md)、[gpt-sol](2026-09-13-r1-gptsol.md)、[任務書](task-r1.md) | Opus 4/4/3/3/3、gpt-sol 3/3/2/4/2 |
| r2 | 2026-09-13 | 同上，fix-r1＋fix-r2 之後 | [Opus](2026-09-13-r2-opus.md)、[gpt-sol](2026-09-13-r2-gptsol.md)、[任務書](task-r2.md) | Opus 5/4/3/3/4、gpt-sol 4/3/3/4/3 |
| r3 | 2026-09-13 | proto4-5（LLM 兩層）＋ proto4-6（逐步 JSON／Python／Lua） | [Opus](2026-09-13-r3-opus.md)、[gpt-sol](2026-09-13-r3-gptsol.md)、[任務書](task-r3.md) | 4-5：Opus 2.5/3.5/3/3/3.5、gpt-sol 4/3/3/-/3；4-6：Opus 4.5/4/3.5、gpt-sol 4/4/3/4/3 |

## r1 兩份合起來的「要改的清單」（Fable 整理，2026-09-13）

兩個人都撞到的排前面。**小**＝文件或一行警告，**中**＝要加旗標或指令。

| # | 問題 | 兩人都提？ | 大小 | 處理 |
|---|---|---|---|---|
| 1 | README 那行 `(import ./src/aos :as aos)` 照抄必壞；其實 aos-step 每格已經把 `aos/*`、`here`、`pc` 綁好 | 是 | 小 | **這輪修**（fix-r1） |
| 2 | 跑一半改 prog.janet，pc 靜悄悄錯位、沒任何警告（兩人都說最危險） | 是 | 小 | **這輪修**：`.aos-step/` 記 form 數＋內容 hash，對不上印一行警告（不擋） |
| 3 | inst.json 沒寫 `stderr`，出錯畫面一片空白 | Opus | 中 | 分兩半：`aos-kernel-init` 印的範例、README 的範例都帶 `stderr`（**這輪修**）；`aos-exec --stderr PATH|-` 覆蓋旗標（**使用者 09-13 拍板做**，fix-r2） |
| 4 | `aos-step --done-exit` 跟 kernel `config.json` 的 `done_exit` 兩套，對不上 cpu 被佔死、`ls` 看不出來 | Opus | 中 | **這輪修**：aos-step 拿掉 `--done-exit`，只認環境變數都不要，寫死 100＝跟 kernel 預設一致；README 寫「這個號碼是 kernel 說了算」 |
| 5 | 開機三步沒人包、排行程要自己 `cp` 進 `procs/` 取檔名 | 是 | 中 | **使用者 09-13 拍板做**（fix-r2）：`aos-kernel-boot K`（語意照 §19.3：只把 kernel 放上 daemon，不開 daemon、不 init）＋ `aos-kernel add [K] inst.json`（自動配名、幫轉絕對路徑、先檢查再排） |
| 6 | `aos-kernel ls` 要先 `cd K`；不顯示 daemon 活著沒、bad 幾件為什麼、最近 done | 是 | 小 | **這輪修**：`ls [DIR]` 可選路徑；頂上加 daemon `alive`／`dead`；多印 `bad: n（最近原因）` |
| 7 | `ctl stop` 之後 `ls` 說「daemon 沒起來過」 | Opus | 小 | **這輪修**：改字 |
| 8 | README「怎麼跑」沒先講 `AOS_DAEMON_HOME`；`&` 在非互動 shell 會跟著死；`ncpu` 不含 kernel 自己那顆；每格會清空 stdout；`form N` 是 0-based 不是行號；cpu 不用自己插 | 是 | 小 | **這輪修**：都是 README 幾句話；錯誤訊息補 `(prog.janet 第 N 個 form)` |
| 9 | 被迫知道 argv 絕對路徑、cwd 寫死、`--home` 不傳子孫 | 是 | 中 | 3 與 5 做了就少一半；`aos-kernel add` 幫轉絕對路徑（**fix-r2**） |

兩人都說好的（別動）：daemon＝硬體／`add`＝插 cpu／kernel＝第一個程序這組比喻；`:read`＋`:json` 一次到位；退件進 `procs/bad/` 且 log 寫原因；`form N 失敗` 加 `.aos-step/error` 雙入口；`init` 跑完印下一步。

## r2 兩份合起來的「要改的清單」（Fable 整理，2026-09-13）

兩人都說 r1 的坑解掉了（上手 5／4 分）。剩下集中在「排錯了怎麼辦」。

| # | 問題 | 兩人都提？ | 大小 | 處理 |
|---|---|---|---|---|
| 1 | 沒有 `aos-kernel rm`：排錯了只能手改 `cpus/N.json` | 是 | 中 | **fix-r3**：做成第一個 syscall——rm 寫一張單進 `K/syscalls/`，tick 每回合先處理（免得跟 tick 搶檔）；正在 cpu 上的也能拿掉；拿掉＝刪掉，不進 `done/` |
| 2 | `add` 不驗欄位；壞 inst.json（多一個 `timeout_ms`）每回合回 125 轉 256 次沒人管，`bad/` 一直空 | Opus | 中 | **fix-r3**：add 與 check_queue 都用 aos-exec 的驗證器；跑起來連續 125 的搬進 `bad/` |
| 3 | `aos-kernel ls`：`PID` 欄裝的是名字（跟 ctl 的 PID 撞）、看不到 exit code、家不存在時吐 Errno 2 | Opus | 小 | **fix-r3**：改叫 `PROC`、加 `LAST_EXIT`、錯誤句跟 boot 同口吻 |
| 4 | README：沒教關機；daemon 常駐沒有一條標準寫法（gpt-sol 環境 nohup 沒留下來、setsid -f 才行）；cwd 可省略沒講；cwd 與 argv[0] 基準不同沒講；規格連結佔開頭、「檔案」長表佔篇幅 | 是 | 小 | **fix-r3**：都補；「檔案」節搬 `docs/files.md`、規格連結搬到底 |
| 5 | proto4-4 README：`:json` key 是字串沒講；每格會印 form 的值沒講；沒教「卡住看 `--status` 的 `:error`」；失敗訊息把 stacktrace 全吐 | 是 | 小 | **fix-r3**：補四句；stderr 只印第一行，全文留 `.aos-step/error` |
| 6 | boot 第一行印 `ok=True result={…}` 一串內臟；add／boot 後 ls 要等下一回合才看得到 | 是 | 小 | **fix-r3**：boot 收掉那行；add 印完加一句「下一回合才會出現在 ls」 |
| 7 | prog.janet 改過：gpt-sol 想預設停住等 `--accept-change`；Opus 說現在這樣完美 | 意見相反 | — | **維持現狀**（使用者 09-13：隨我定；Opus 說這樣剛好） |
| 8 | 沒有「健不健康」的顯示；done_exit=100 沒有名字 | 各一 | — | **不做**（使用者 09-13：隨我定） |

## r3 兩份合起來的「要改的清單」（Fable 整理，2026-09-13）

逐步執行器三支兩人都說好用（4～4.5），`wait_for` 是最受歡迎的東西。坑集中在 LLM 那層的第一步，和「kernel 看不出行程在等」。

| # | 問題 | 兩人都提？ | 大小 | 處理 |
|---|---|---|---|---|
| 1 | proto4-5 README 沒有 `endpoints.json` 完整範例，照 README 寫出來一定退 2（Opus 卡最久）；結果檔九成是 `raw`，`--wait` 整份倒到終端機；欄位沒分「日常／除錯／原始」 | 是 | 小 | **fix-r4a**：README 貼完整範例＋欄位分三組；`--wait` 成功只印 `text`＋結果檔路徑 |
| 2 | module 自動生的 `K/llm/endpoints.json` 內建 DeepSeek（要錢）且 enabled；local 的 model 是佔位字串，README 沒說要改哪格 | 是 | 小 | **fix-r4a**：預設檔只留 local（其他範例搬文件），README 補「把 model 換成 `aos-llm models` 看到的 id」 |
| 3 | 模型名打錯照樣送出去、燒完 token 才判 `model_mismatch`；失敗時 `model` 欄意思會變 | 是 | 中 | **fix-r4a**：`strict_model` 的 endpoint 送出前先比對 `/models`，沒有就回 `model_not_found` 不花錢；`model` 一律是對方回的（沒回就 null），設定值看 `model_requested` |
| 4 | `--wait` 逾時／daemon 沒回應時退 1，但那張單還留在 `syscalls/`，daemon 回來照跑（gpt-sol 第一名） | gpt-sol | 中 | **fix-r4a**：逾時時單子還沒被撿走就撤掉並說「沒送出」；已被撿走就說「已送出，結果會在 X」 |
| 5 | `--reset` 之後重跑，`llm_submit` 同名撞 `id 已經存在` 卡死在同一格 | Opus | 小 | **fix-r4a**：同名且請求內容一模一樣＝視為同一張，回原結果路徑不報錯；內容不同才擋 |
| 6 | 行程在 `wait_for` 等一個永遠不來的檔，`ls` 跟健康行程長一樣、還永久佔一顆 cpu；連續失敗的行程也一樣看不出來、永遠重跑 | 是 | 中 | **fix-r4b＋4c**：執行器等檔沒到改退 **101**（等待碼，跟 100 一樣由 kernel `config.json` 說了算）；kernel 看到 101 標 `waiting`、有人排隊就讓出 cpu；連續非零退出 N 次進 `bad/`（`bad_after`，預設 10） |
| 7 | Lua `aos.b64` 回純字串，跟自動的 `{"$b64":…}` 兩種長相並存、只有後者讀回會還原；Lua `ms` 恆 0（`os.clock` 是 CPU 時間）；`aos-step-lua --help` 不認得；`return` 表漏列函式沒任何警告 | 是 | 小 | **fix-r4b**：`aos.b64` 改回 `$b64` 物件、`unb64` 兩種都吃；`ms` 改牆鐘；補 `--help`；檔裡有 `function 名` 沒進 return 表就警告一句 |
| 8 | `.aos-step-py/error` 一個資料夾一份會互蓋；README：Python 那節沒列 `aos.call` 選項、`out.req.json` 該寫 `<OUT>.req.json`、wait 會先推 pc 要畫時間線、`llm_submit` vs `llm` 是「兩個家」沒講、`--reset` 不會清輸出檔沒講 | 是 | 小 | **fix-r4b**：錯誤全文改 `<PROG>.error`（三支一致）；README 五句 |
| 9 | proto4-3 README：範例 `K` 長在 repo 裡、`./aos-kernel` 與 `aos-kernel` 混用、init 沒帶 `--module` 事後補不了沒講；`ls` 把「找不到 daemon 家」也印成 `daemon dead` | Opus | 小 | **fix-r4c**：範例改絕對路徑、統一 `./`、init 那行加註解；`ls` 分開講 |
| 10 | 程式跑一半改動要預設停住（gpt-sol 又提） | gpt-sol | — | **不做**（r2 #7 已定維持現狀） |
| 11 | `add` 之後 `ls` 要等下一回合；`procs/` 的 id 會回收跟 done 擺一起易誤會 | 各一 | — | **先不動**（CLI 已提醒；id 回收下輪再看） |

兩人都說好的（別動）：三支 `--status`／`--reset`／`--stderr` 一致；Python 例外訊息「第幾格、哪個函式、第幾行、全文在哪」滿分；`aos.call(..., args=)` 不用管 quoting；`ls` 的 `llm:` 狀態列一眼看懂容量；退出碼 0／1／2 跟 README 完全一致。

## 修的批次（每批一本任務書，派 codex gpt-sol；回報放同名 `-out.md`）

| 批 | 做哪些 | 任務書 |
|---|---|---|
| fix-r1 | #1、#2、#3 前半、#4、#6、#7、#8 | [fix-r1-task.md](fix-r1-task.md) |
| fix-r2 | #3 後半 `--stderr`、#5 boot＋add、#9 轉絕對路徑 | [fix-r2-task.md](fix-r2-task.md) |
| fix-r3 | r2 清單 #1–#6（rm 當第一個 syscall、驗欄位＋125 進 bad、ls 欄位、文件） | [fix-r3-task.md](fix-r3-task.md) |
| fix-r4a | r3 清單 #1–#5（proto4-5：README 範例、預設只留 local、模型先比對、--wait 逾時撤單、同名同內容不報錯） | [fix-r4a-task.md](fix-r4a-task.md) |
| fix-r4b | r3 清單 #6 執行器側（退 101）、#7、#8（proto4-6＋proto4-4 aos-step） | [fix-r4b-task.md](fix-r4b-task.md) |
| fix-r4c | r3 清單 #6 kernel 側（101＝waiting、讓 cpu、bad_after）、#9（proto4-3） | [fix-r4c-task.md](fix-r4c-task.md) |
