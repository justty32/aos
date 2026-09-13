# 試玩紀錄（play）

← [筆記索引](../2026-09-08-ideas.md)｜規則在 [§21.5](../20-21-step-lisp-and-next.md)

每個段落收線後，開沒看過設計筆記的 agent 只拿 README 當新使用者玩，照五條標準打分（① 容易上手 ② 容易理解 ③ 複雜藏好 ④ 外層簡單但全面 ⑤ 少背）。一輪一列。

| 輪 | 日期 | 玩什麼 | 報告 | 分數（①②③④⑤） |
|---|---|---|---|---|
| r1 | 2026-09-13 | proto4-3（OS 層）＋ proto4-4（逐步 lisp） | [Opus](2026-09-13-r1-opus.md)、[gpt-sol](2026-09-13-r1-gptsol.md)、[任務書](task-r1.md) | Opus 4/4/3/3/3、gpt-sol 3/3/2/4/2 |
| r2 | 2026-09-13 | 同上，fix-r1＋fix-r2 之後 | [Opus](2026-09-13-r2-opus.md)、[gpt-sol](2026-09-13-r2-gptsol.md)、[任務書](task-r2.md) | Opus 5/4/3/3/4、gpt-sol 4/3/3/4/3 |
| r3 | 2026-09-13 | proto4-5（LLM 兩層）＋ proto4-6（逐步 JSON／Python／Lua） | [Opus](2026-09-13-r3-opus.md)、[gpt-sol](2026-09-13-r3-gptsol.md)、[任務書](task-r3.md) | 4-5：Opus 2.5/3.5/3/3/3.5、gpt-sol 4/3/3/-/3；4-6：Opus 4.5/4/3.5、gpt-sol 4/4/3/4/3 |
| r4 | 2026-09-13 | 只驗 LLM 層（fix-r4 之後） | [Opus](2026-09-13-r4-opus.md)、[gpt-sol](2026-09-13-r4-gptsol.md)、[任務書](task-r4.md) | Opus 4/4/4/3/4、gpt-sol 3/3/3/4/2 |
| r5 | 2026-09-13 | 只拿 `playground/README.md` 玩六站（使用者今晚會走的路） | [Opus](2026-09-13-r5-opus.md)、[gpt-sol](2026-09-13-r5-gptsol.md)、[任務書](task-r5.md) | 一個總分：Opus 4/5、gpt-sol 3/5 |

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

## r4 兩份合起來的「要改的清單」（Fable 整理，2026-09-13）

兩人都確認 fix-r4a 的三個重點真的修好了：模型名打錯 4 ms 就擋、不花 token；daemon 沒開丟單會撤、重開不偷跑；`--reset` 重跑同名同內容不卡。Opus 說「挑不出該動程式的地方」。剩下全是小的。

| # | 問題 | 兩人都提？ | 大小 | 處理 |
|---|---|---|---|---|
| 1 | proto4-5 quickstart 沒寫要先 `aos-daemon`、`aos-kernel-boot`；`./aos-llm` 跟 proto4-3 的 PATH 慣例不一致 | 是 | 小 | **fix-r5**：補兩行、統一成 PATH 慣例 |
| 2 | proto4-6 Python 節：`llm_submit(K, req, name) -> 結果檔路徑`、`wait_for` 沒寫簽名，範例的 `K` 沒交代從哪來；`llm` vs `llm_submit` 是兩個家只寫在 Lua 節；狀態檔名算不算公開介面沒說 | 是 | 小 | **fix-r5**：完整三格範例＋`K = "/abs/K"`、簽名、兩個家、狀態檔名是公開的 |
| 3 | 自動生的 `K/llm/endpoints.json` 是一行 minified、model 是 `loaded-model-id`，提醒只在 kernel.log；`ls` 看不出還沒換 | 是 | 小 | **fix-r5**：寫檔 indent=2；`aos-kernel-init --module` 畫面直接印提醒；`ls` 的 `llm:` 行在還是 placeholder 時加「model 還沒換」 |
| 4 | 同名不同內容撞牆的訊息沒說怎麼解（要刪 `K/llm/results/<name>.json` 或換名字）；沒有查單／清單的指令，看排隊只能靠 `ls` 一行，清結果只能自己 rm | 是 | 中 | **fix-r5**：訊息補一句；加 `aos-kernel llm ls K`（queued／running／done＋結果路徑）與 `aos-kernel llm rm K NAME` |
| 5 | kernel 沒活著時不帶 `--wait` 也會撤單，README 說「不想等就省略 --wait 由下一回合處理」會誤會 | Opus | 小 | **fix-r5**：README 補一句 |
| 6 | `--reset` 後 `<PROG>.error` 還在，`--status` 先噴上次整段 traceback | Opus | 小 | **fix-r5**：`--reset` 一併刪 `<PROG>.error` |
| 7 | `ls` 最多落後一回合（結果檔在了還顯示 running 1、WAIT 一度是 `-`） | 是 | 小 | **fix-r5**：README 一句「ls 看的是上一回合的帳」 |
| 8 | 剛換上 cpu、RUNS=0 時 `LAST_EXIT` 印前一個佔位者的碼（Fable 自己看到的） | — | 小 | **fix-r5**：換人時清掉 |
| 9 | 撞名這種必死的錯還被 `bad_after` 白試 10 次 | Opus | — | **不做**（kernel 分不出哪種錯會自己好，10 次一秒一次可接受） |
| 10 | `WAIT` 欄補上在等哪個檔 | Opus | — | **不做**（kernel 不讀行程的狀態檔，只認退出碼） |

## r5 兩份合起來的「要改的清單」（Fable 整理，2026-09-13 晚）

六站有五站兩人都照抄一次過；agent 那站兩人都說最好玩（Opus：「第三次回答還會講 messages.json 變大了，記憶是真的有接上」）。坑集中在「重玩一次」。

| # | 問題 | 兩人都提？ | 處理 |
|---|---|---|---|
| 1 | 做完的行程留在 `done/`，同名再 `add` 被擋、`rm` 又說找不到，只能手動刪檔（第 3 站重玩死路） | Opus | **fix-r6**：`rm` 連 done／bad 一起清；`add` 撞 done 自動清 |
| 2 | 連丟兩封信，第二封插隊 | gpt-sol | **fix-r6**：一題一封信 |
| 3 | `--reset` 後改問題撞 LLM 單名 | 是 | **fix-r6**：state 加 `epoch`，reset 加一，請求名帶 epoch |
| 4 | `listen --once` 秒回全部舊回話像跳針 | 是 | **fix-r6**：只印沒印過的，沒有就說「沒有新回話」；指南先改用 `--new --once` |
| 5 | `playground/down.sh` 相對路徑在別的目錄照抄找不到；橫幅 `$K` 沒展開；README 沒說 `AOS_PLAY` 可換 | 是 | **已改**：腳本改名 `play-up`／`play-down`／`play-reset` 放進 PATH；橫幅印真路徑；補一句 |
| 6 | 第 5 站「第四次開始等」數錯（第五次才 101）；第 2 站 add 後要等一回合 | 是 | **已改**：指南 |
| 7 | 指南第 1 站 `max_tokens` 那段跟實測不符（要放 `params` 裡） | Opus | **已改**：指南 |
| 8 | daemon 正常收工後 `ls` 說「找不到 daemon 的家」；RUNS 印 `None`；名字長欄位歪 | Opus | **fix-r6** |
| 9 | 逐步執行器成功不出聲；Python 例外一行訊息行號指到 def | Opus | **fix-r6** |
| 10 | stuck 的用詞（outbox 說「先停」、status 說 stuck） | 是 | **fix-r6**：統一 |
| 11 | 撞名這種要改設定的錯 5 秒就被 `bad_after` 退件，來不及照提示做 | Opus | **不做**（kernel 分不出；epoch 之後這條路本身就少了） |

## 修的批次（每批一本任務書，派 codex gpt-sol；回報放同名 `-out.md`）

| 批 | 做哪些 | 任務書 |
|---|---|---|
| fix-r1 | #1、#2、#3 前半、#4、#6、#7、#8 | [fix-r1-task.md](fix-r1-task.md) |
| fix-r2 | #3 後半 `--stderr`、#5 boot＋add、#9 轉絕對路徑 | [fix-r2-task.md](fix-r2-task.md) |
| fix-r3 | r2 清單 #1–#6（rm 當第一個 syscall、驗欄位＋125 進 bad、ls 欄位、文件） | [fix-r3-task.md](fix-r3-task.md) |
| fix-r4a | r3 清單 #1–#5（proto4-5：README 範例、預設只留 local、模型先比對、--wait 逾時撤單、同名同內容不報錯） | [fix-r4a-task.md](fix-r4a-task.md) |
| fix-r4b | r3 清單 #6 執行器側（退 101）、#7、#8（proto4-6＋proto4-4 aos-step） | [fix-r4b-task.md](fix-r4b-task.md) |
| fix-r4c | r3 清單 #6 kernel 側（101＝waiting、讓 cpu、bad_after）、#9（proto4-3） | [fix-r4c-task.md](fix-r4c-task.md) |

**fix-r4 落地補記（2026-09-13 傍晚）**：三本同時派、都交了（回報 `fix-r4{a,b,c}-out.md`）。測試 proto4-3 236、proto4-5 56、proto4-6 77、Janet 42／46／12 全綠。Fable 真開 daemon 跨邊界驗過：等檔的行程 `ls` 顯示 `waiting 等了 N 回合`，只有一顆 cpu 時有人排隊它就讓位、別人做完再回來；`aos-kernel llm --wait` 只印答案＋結果檔路徑；同名同內容退 0、不同內容退 1 並說撞在 running。**順手看到的小毛病（下輪清單）**：剛換上 cpu、RUNS=0 時 `LAST_EXIT` 印的是前一個佔位者的碼（等的人會被印成 100）。
| fix-r5 | r4 清單 #1–#8（全小：README 五處、endpoints 排版與提醒、`aos-kernel llm ls/rm`、reset 刪 error、LAST_EXIT） | [fix-r5-task.md](fix-r5-task.md) |

**fix-r5 落地補記（2026-09-13 晚）**：八條全做（回報 `fix-r5-out.md`）。測試 proto4-3 237、proto4-5 63、proto4-6 77、Janet 42／48／12 全綠；`aos-kernel llm ls K`／`rm K NAME` 在遊樂場真跑過。r4 循環到此停：Opus 說挑不出該動程式的地方。
| fix-r6 | r5 清單 #1–#4、#8–#10（kernel rm／add 清 done、ls 訊息與表格；執行器出聲與行號；agent 一題一封、epoch、listen --once、stuck 用詞） | [fix-r6-task.md](fix-r6-task.md) |
