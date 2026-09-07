# 玩的紀錄總表（2026-09-06）

這張表把 17 個包和 1 條端到端整合線濃縮起來；整合線有兩份紀錄，所以一共讀了 19 個來源檔。

| 紀錄 | 那輪做什麼 | 玩的結果一句 |
|---|---|---|
| [hooks](2026-09-06-hooks.md) | 補工具包共用掛勾與 `Ctx` 接點 | 後面的包能各寫各的；掛勾壞掉也不會拖死 agent。 |
| [bigmem](2026-09-06-bigmem.md) | 長記憶、外部記憶世界與 ref | 三筆記憶能存、能找；但結果要下一輪才收，不能原地等。 |
| [branch](2026-09-06-branch.md) | 同題分三條旁線思考，再合流或採用 | 三條都回來並選出方案；第三條因共用 LLM 額度晚一輪。 |
| [code](2026-09-06-code.md) | 搜尋、存復原點、檢查、看差異、撤銷 | 型別註記、語法檢查和測試都成功；模型沒有完全照建議順序。 |
| [communication](2026-09-06-communication.md) | agent 寄信、回信與等信 | A 問、B 回、A 收到提醒整條走通；別名和世界名不同時會回不了。 |
| [cost](2026-09-06-cost.md) | 記每輪工具、token、時間與價錢 | 三次 shell 都入帳；引擎沒單價，所以金額誠實地顯示 `null`。 |
| [fs](2026-09-06-fs.md) | 讀寫、修改、列目錄與短指令 | 寫程式、改數字、重跑都一次成功；路徑與同時寫入仍沒保護。 |
| [identity](2026-09-06-identity.md) | 身份、乾淨環境與秘密注入 | agent 看不到金鑰，LLM 看得到且能工作；自己的鐘最後都有收掉。 |
| [jobs](2026-09-06-jobs.md) | 把長指令交給獨立時鐘執行 | `sleep 15` 沒卡住 agent，完成後寄信回報，工作鐘自己消失。 |
| [kids](2026-09-06-kids.md) | 生、列、停、續、收子 agent | tom 算出 391 並自動回報；簡單乘法卻繞了 84 格。 |
| [mcp](2026-09-06-mcp.md) | 用 MCP 建世界、開鐘、說話、聽回覆 | 從外面替使用者說話成功；agent 與 LLM 仍要各開一顆鐘。 |
| [newagent](2026-09-06-newagent.md) | 用模板建立頂層 agent | coder 能載包並看資料夾；小事跑到 66 格，還把 `dir` 看成路徑。 |
| [review](2026-09-06-review.md) | 回顧成本、找壞習慣、寫教訓 | 能抓到重複 shell 並寫下教訓；固定句型連錯兩次才成功。 |
| [sched](2026-09-06-sched.md) | 替 LLM 請求排優先順序與分帳 | 五筆開工順序完全符合分數；有兩筆模型本身慢到約 63 秒。 |
| [selfmem](2026-09-06-selfmem.md) | 看自己、壓縮對話、存找筆記 | 48 則舊對話壓成摘要後剩 15 則；模型也會太勤快地存筆記。 |
| [think](2026-09-06-think.md) | 單段或多段深思，再收斂結論 | 能保住前一步的可用結論；但 5999 token 可能全花在隱藏思考。 |
| [toolsmith](2026-09-06-toolsmith.md) | agent 自己新增、試跑、關閉工具 | `today` 當格造好並試跑成功；正式工具要下一格才載入。 |
| [integration](2026-09-06-integration.md)／[whole-system](2026-09-06-whole-system.md) | 模板、生子、回信、重啟與整套操作 | 六段父子鏈和重啟都走通；也抓到啟動、錯誤回報與結果所有權問題。 |
| [simplify-2](2026-09-07-simplify-2.md) | 旁線牆鐘逾時與每題動作格 | 睡三格不吃題目上限；醒來那格才續算，缺鐘另報 `no_clock`。 |
| [studio-2](2026-09-07-studio-2.md) | 公司 ollama 重跑工作室，驗預算硬閘門 | 個人 token 門會擋下一筆 LLM；整隊 ticks 在 idle 時穿透到 458/300，沒有自動停鐘。 |
| [studio-3](2026-09-07-studio-3.md) | 公司 ollama、預算五百萬重跑工作室，看交不交得出來 | 沒交付；token 第 6 分鐘後靜止、55 分鐘 idle 空轉，PM 已通知未讀的信永不重喚醒，chief 以下四人從沒開工。 |
| [studio-4](2026-09-07-studio-4.md) | 修掉卡死、每格守額度、再把流程做成工具（studio／pyshop 包），三局實玩 | 4b 寫出 todo.py 且測試全過；4c 新流程接單→派工→自動撥款→回報退回→驗收全自己走，但 dev 模型改不出配測試的程式，沒交付；4d 換八人＋claude-cli（haiku／sonnet）**整條走到交付**，成品跑得過。過程在 [journey](../2026-09-07-studio-journey.md)。 |

## 最常撞到的坑

- **模型不照工具說明走。** 會漏參數、叫錯工具、把輸出欄位當路徑、重複查、自己猜結論；最後常能恢復，但小事會燒很多格。（code、kids、newagent、review、think、integration）
- **旁線結果不是當格回來。** 模型若原地輪詢，就會「自己等自己」；正確做法是先回話，等下一次被喚醒。（bigmem、branch、think、jobs）
- **共用 LLM 會排隊，也會忽快忽慢。** 兩個額度滿了，第三筆自然晚到；短題也可能跑一分鐘。（branch、sched、mcp、whole-system）
- **reasoning 很會吃額度，還可能沒有正文。** 深思不等於正確，也不保證拿得到可顯示的答案。（think、sched、whole-system）
- **shared 鐘和 own 鐘容易混。** shared 小孩掛父的 inst；own 小孩、agent、LLM 各有自己的鐘。漏開一顆時，表面只像沒回話。（kids、mcp、whole-system、jobs）
- **接點不夠時，各包只好自己繞。** 直接讀 `state.json`、`clocks/`、`.aos/inst`、結果檔或 `prompts.json`，能跑但責任散掉。（bigmem、branch、code、cost、kids、selfmem、newagent、review）
- **world、home、相對路徑和別名不是同一件事。** 算錯基準會把請求送到沒鐘的地方；通訊錄別名也可能讓回信找不到人。（communication、identity、kids、toolsmith、code、fs）
- **測試會互相干擾。** 並行輪會改共用包、帳本和進程；舊的殘留檢查甚至會誤傷正在工作的鐘。（hooks、code、identity、newagent）
- **檔案並行與原子性普遍未補。** 多進程同寫可能互蓋，斷電可能留下半份結果，微秒檔名也可能相撞。（hooks、fs、jobs、bigmem、branch、communication、cost、review、selfmem、think、toolsmith）
- **狀態和錯誤不夠好找。** `status` 沒顯示當前 state，LLM 壞掉曾只讓使用者乾等，成功 worker 的 log 又可能是空的。（cost、mcp、whole-system）
- **格式與欄位曾各說各話。** requester、token 名、截斷長度、模板工具優先權都出現過兩套說法。（fs、sched、selfmem、integration）
- **預算檢查點不等於資源停止點。** 閘門只在要送 LLM 時檢查，但 idle step 仍計入 ticks；零額度還被當成不設個人上限。（studio-2）

## 介面簡不簡潔

| 包名 | 自評 | 哪裡可以更簡 |
|---|---:|---|
| hooks | 8/10 | `put_mail` 不要同時接受名字和路徑。 |
| bigmem | 8/10 | 歸檔「最舊幾則」，不要叫人算序號。 |
| branch | 8/10 | `budget` 可再短，但單位要保留。 |
| code | 8/10 | 目前已很短；checkpoint 的檔案範圍仍應明講。 |
| communication | 8/10 | 別名和世界名不該要求一致。 |
| cost | 8/10 | 共用層若自動記帳，包只剩查詢。 |
| fs | 9/10 | 截斷資訊可留，但輸出格式要避免把 `dir` 當路徑。 |
| identity | 8/10 | 安全模式不該還要手寫 `legacy_env: false`。 |
| jobs | 9/10 | 先維持四工具；真需要時才加最長時間。 |
| kids | 8/10 | `kids_list` 應直接顯示 `alive`。 |
| mcp | 8/10 | agent 與 LLM 可用一個高階入口成對開鐘。 |
| newagent | 8/10 | `--prompts` 應更明白表示它吃檔案路徑。 |
| review | 7/10 | 「上一個任務」不該讓模型猜格數；教訓句型也太硬。 |
| sched | 8/10 | requester 不該在頂層和 priority 出現兩次。 |
| selfmem | 8/10 | 摘要取出與替換分兩支工具，不太直覺。 |
| think | 8/10 | `id` 和 `thought_id` 應統一。 |
| toolsmith | 9/10 | `tool_add` 同時管 shell 工具和 pack 骨架，責任稍混。 |

最該簡化的三個介面：

1. 旁線請求收成「送出、睡著、收回、逾時、取消」一套，模型不用輪詢。
2. `status` 直接說目前狀態、正在等哪筆、哪顆鐘沒跑、最後錯在哪。
3. world／home／路徑／通訊錄名字都由 `Ctx` 解析，包只拿穩定把手。

## 內部機理簡不簡單

| 包名 | 自評 | 哪裡可以更簡 |
|---|---:|---|
| hooks | 8/10 | pending 還要記包名，再載回原包。 |
| bigmem | 8/10 | 缺接點，才多 pending 摘要與下一輪替換。 |
| branch | 7/10 | `join`、`adopt` 各有一段繞路。 |
| code | 8/10 | checkpoint 要另記原本不存在的檔。 |
| communication | 8/10 | 每格會重掃已讀與未讀信。 |
| cost | 7/10 | 補帳要重寫當日檔，摘要還要重算。 |
| fs | 8/10 | shell 逾時要管整個行程群組。 |
| identity | 8/10 | 設定沿用現有時鐘 JSON，沒有另開系統。 |
| jobs | 8/10 | 完成器塞成一條很長的 Python 指令。 |
| kids | 7/10 | 先生孩子再補檔，中途失敗沒有回滾。 |
| mcp | 8/10 | 只有建世界與投信不是單純包 CLI。 |
| newagent | 未打分 | 建頂層世界和 `spawn()` 有重複程式。 |
| review | 8/10 | 同一帳本被多支工具反覆掃，單檔已約五百行。 |
| sched | 8/10 | 只靠 JSON、mtime 和最近十筆狀態。 |
| selfmem | 8/10 | 摘要分兩格，靠 state 暫存筆數。 |
| think | 8/10 | 自己讀 engine、估價、整理 usage，佔掉不少程式。 |
| toolsmith | 9/10 | 一檔完成；骨架就是普通 Python。 |

最該簡化的三個內部：

1. 共用層統一擁有 request／running／result／done，收件者不能和 LLM 搶著搬結果。
2. 共用原子寫入、鎖、增量索引與清理工具，別讓每包各自全量掃描重寫。
3. `new`、`spawn`、template 共用一個建世界流程，工具包優先權只留一條規則。

## 效能與邊緣狀況（留給使用者拍板）

- kernel 剛 start 就 register 曾誤報沒在跑；第二輪已修過，但這是第一個會撞到的啟動競速。（whole-system）
- agent 與 LLM 少開任一顆鐘，都可能只表現成「一直沒回」；逾時提示已補過一版。（mcp、whole-system）
- 小模型會亂繞、重複查或誤讀工具輸出，簡單任務也可能跑數十格。（newagent、kids、review、think）
- 模型可能把額度全花在 reasoning，最後正文空白；深思結果也未必正確。（think、whole-system、sched）
- 共用引擎有併發上限；請求會排隊，單筆也可能慢到一分鐘。（branch、sched、mcp）
- 引擎沒單價時成本只能是 `null`；估價、token 分攤和「今日用量」口徑也未完全可靠。（branch、cost、review、selfmem、think、whole-system）
- consumer 拿走 result 後，LLM 曾又補 `worker died`，造成重複錯誤與灌水用量。（whole-system）
- 並行測試會碰共用帳本、工具清單與進程；殘留檢查可能誤判。（hooks、code、identity、newagent）
- 多數 JSON、對話、筆記與工具設定沒有鎖，同時寫可能互蓋。（hooks、fs、jobs、bigmem、branch、cost、review、selfmem、think、toolsmith）
- 有些寫入不是原子換檔；斷電可能留下半個檔或結果與信不同步。（fs、jobs）
- job 在結果落盤前死掉會整個重跑；請求重送和副作用去重普遍沒做。（jobs、bigmem、branch）
- 長工作、旁線思考和已送 LLM 請求缺完整取消；job 也沒有總併發上限。（branch、jobs、think）
- toolsmith 的 shell 沒逾時、沙箱或危險指令審批，卡住就卡一格。（toolsmith）
- `../`、絕對路徑與 symlink 可能走出世界；相對 home／world 算錯也會投到錯地方。（fs、code、kids、toolsmith、newagent）
- 通訊錄別名、世界名與寄件人不一致會讓回信失敗；名字也可冒用。（communication、sched）
- legacy 環境會整包複製；秘密檔權限檢查和真正讀檔之間仍有競速。（identity）
- 世界搬家後，contacts、parent、kids 的絕對路徑不會自己修。（hooks）
- 信箱、pending、帳本、筆記、refs、工具、分支與排程多了後，許多操作都是全量掃描。（hooks、bigmem、code、communication、cost、kids、review、sched、selfmem、think、toolsmith）
- 大檔、完整 log、完整 diff 或整包 archive 會整份進記憶體。（code、fs、jobs、mcp）
- jobs、thoughts、forgotten、undo、舊分支與 refs 都沒有完整清理政策，磁碟會一直長。（bigmem、branch、code、jobs、selfmem、think）
- 同一微秒寄信、同 id、同建立路徑或重用孩子名字的碰撞未完整處理。（hooks、communication、branch、kids、mcp、newagent）
- 非 UTF-8、二進位檔、權限、壞 JSON／JSONL、循環 ref 和檔案被搬走，多半只做最直白處理。（bigmem、code、fs、review）
- 跨午夜、時區、壞 deadline 與不到一分鐘的等待分，現在都是粗略規則。（cost、review、sched）
- 等信逾時、送達確認、退信重試、廣播迴圈、跨機器與父死後孤兒鐘都還沒做。（communication、kids）
- 模板內容驗證、私有包、同名工具優先與重跑覆蓋，仍有容易出現舊檔或選錯工具的角落。（fs、mcp、newagent、toolsmith、integration）

## 各包想要但還沒有的接點

- `bigmem`：記憶世界專用的 `mem_send`／`mem_take`。
- `bigmem`：安全的 `history_read`／`history_replace`。
- `bigmem`：送主線 LLM 前可以擋下請求的掛勾。
- `branch`：當格取回指定旁線結果的共用接口。
- `branch`：讓 `adopt` 明講「這次不要追加舊工具結果」的接口。
- `code`：安全解析世界內路徑的 `project_path`，以及統一的 `undo_dir`。
- `communication`：`put_mail` 自動把首封檔名當 thread。
- `communication`：用世界路徑反查通訊錄名字。
- `cost`：`on_act` 還拿不到模型送來的原始參數字串與統一錯誤種類。
- `kids`／`self`：只讀的 daemon 時鐘狀態接口。
- `mcp`：指定來源投信進 agent inbox 的共用 CLI。
- `newagent`：`aos_agent.py` 裡可供 `new` 與 `spawn` 共用的頂層世界建立函式。
- `review`：目前任務編號、粗略 task key 與上次任務起始格。
- `think`：每格都會叫的 `on_tick`。
- `think`：旁線完成前暫停主線 LLM 的接口。

## 如果只修三件

1. 先把非同步生命週期收乾淨：結果只有一個主人，等待會睡，失敗、逾時與缺鐘直接回到聊天端。
2. 再統一路徑、身份與時鐘：包不再自己猜 world／home、讀 inst、翻 clocks 或反查別名。
3. 最後補共用的原子寫入、鎖、增量掃描與清理；包多、資料多、agent 多時才不會一起變慢或互蓋。
