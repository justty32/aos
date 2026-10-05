# proto7-2 名詞表（白話版）

← [追進度導讀](catch-up.md)｜正式定義在 [spec.md](../spec.md)、各包 README

三欄：白話說法｜正式名稱（文件裡會看到的字）｜一個例子。按「從外到內」排：先空間與時間，再任務，再判定，再包。

## 空間與時間

| 白話說法 | 正式名稱 | 一個例子 |
|---|---|---|
| 整個系統的根目錄，daemon 看守的範圍 | 空間根（root）、`.aosd/` | `/tmp/sp`，裡面的 `.aosd/` 放 daemon 的登記清單、狀態、控制檔 |
| 一個工作站：一個被登記的資料夾，有自己的回合 | **node**、`.aos/` | `/tmp/sp/team`，裡面的 `.aos/` 放任務表、回合檔、槽 |
| 背景常駐的管理員程式 | **daemon**（`aos7-daemon`） | 每個 node 一條時間線，時間到就起 tick、tock |
| 一個 node 的一次「開始到結束」的時間段 | **回合**（round） | `round.json` 記第幾回合、開著還是關了 |
| 開回合 | **tick**（`aos7-tick`） | 回合數加一，照任務表起任務 |
| 關回合 | **tock**（`aos7-tock`） | 判每個槽的狀態、寫總結、通知任務 |
| 幾秒一回合 | interval（在 `timeline.json`） | `{"interval": 5}`＝五秒一回合 |
| 任務都結束就提早關回合（可選，預設關） | **early_tock** | `{"early_tock": true}` |
| 「上一回合的總結」，只留最新的一份 | `last-round.json` | 誰起了、誰結束了、誰走失、有什麼錯 |
| 一個 node 的任務擁有另一個子空間，並在裡面跑自己的 daemon | **子 daemon**、子根（subroot）、子 daemon 包（**subd**） | 父 node 裡的任務用 `aos7-subd` 包裝程式起一個子空間的 daemon |

## 任務

| 白話說法 | 正式名稱 | 一個例子 |
|---|---|---|
| 唯一的任務表 | `tasks.json` | `{"tasks":[{"name":"hello","argv":["sh","-c","echo hi"]}]}` |
| 常駐任務：槽空了就補起來 | `mode: "keep"` | 歷史 module、step 直譯器、adapt 都是 keep |
| 每回合起一次，上一次還沒結束就跳過 | `mode: "each"`（預設） | 每回合抄一次資料 |
| 起一次就從表上刪掉 | `mode: "once"` | step 派的子工作、重啟時加的那一項 |
| 任務的固定資料夾，照名字重用 | **槽**（slot）、`.aos/tasks/<名字>/` | `hello` 的槽永遠是 `.aos/tasks/hello/` |
| 同名任務最多幾個同時跑（＝開幾個槽） | `max_live` | `max_live: 3` → 槽 `job`、`job.1`、`job.2` |
| 一次執行，有遞增流水號 | **run**、run 號 | `hello#57`＝第 57 回合起的那次 |
| 槽名（任務的身分） | **tid** | 環境變數 `AOS7_TID` |
| 這次 run 的出生證明 | `birth.json` | 槽名、run 號、回合、命令、起動者 pid |
| 任務結束的紀錄（帶 run 號） | `exit.json` | `{"run": 57, "code": 0}`；走失時 `"lost": true` |
| 起任務的包裝程式，負責寫 pid、exit、輸出 | **runner**（`aos7-run`） | tick 不直接起任務，經它起 |
| 一次性任務「起了沒」的標記，防被砍後重起 | **launch 標記** | tick 寫 birth 前先在表上那一項記 `launch` |
| 第幾回合起才起 ／ 過了第幾回合就不再起 | `from_round`、`until_round` | 「第 10 回合跑一次」 |
| 任務表的欄位，核心不看內容、原樣抄進 birth | **`x` 透傳** | 模組放自己的資料，例如請求編號 |
| 用另一種格式（inst JSON）描述任務，由 `aos-exec` 跑 | **inst**（搬自 proto7-1） | `"inst": "jobs/a.json"` 取代 `argv` |
| 讓任務搆得到別的資料夾 | **掛載**（mounts）、`mount_allow` | adapt 掛鄰居 node 的 `out/` |
| 給任務的控制請求（砍掉） | 槽的 `ctl.json`、**kill 帶 run** | `{"op":"kill","run":57}`，換人了就不執行 |
| 給 daemon 的控制請求 | `.aosd/ctl/*.json`、**回條**（`ctl-done/`） | 登記、取消登記、暫停、喚醒、停止 |
| 暫停帶名牌：誰下的暫停只有誰能解 | **pause owner** | 預算包暫停的，人來 resume 不會解掉 |

## 判定與錯誤

| 白話說法 | 正式名稱 | 一個例子 |
|---|---|---|
| 推定一件事只有是／否／不知道；不知道不能當否 | **三態判定** | /proc 讀不到 → 不殺、不判走失、不起新 run |
| 任務不見了、也查不到結束紀錄 | **lost**（走失） | 程序被 OOM 砍掉、pid 檔沒寫到 |
| 證據兜不起來，什麼都不做、下一圈再看 | **unknown**（U 不知道）、退出碼 3 | 檔案半寫、/proc 讀不到、鎖拿不到 |
| 錯誤先分四類，同類只走一條路 | **錯誤四分支**：N 不存在／U 不知道／B 輸入不合／K 中斷 | 別人寫的壞檔＝拒收那一件（B）；自己寫的壞檔＝不知道（U） |
| 懷疑走失時，先在系統裡找「node＋槽＋run」都對得上的程序 | **身分掃描** | 找到了就先收掉再判走失，確定沒有才判 |
| 從沒真的跑起來過（有 birth、沒 pid、輸出是空的） | `never_started` 事實欄 | once 保證包靠它決定要不要補跑 |
| 誰的錯：呼叫方沒守規矩 | **M 誤用** | 不拿鎖直接改任務表 |
| 誰的錯：環境出事 | **X 外部故障** | 被 kill -9、磁碟 I/O 錯 |
| 誰的錯：組件沒兌現承諾 | **B 組件 bug** | 讀不到被當成不存在 |
| 誰的錯：契約卡上根本沒寫到 | **G 契約缺口** | 先補卡，再重新分類 |
| 每個組件一張：負責什麼／對方要先保證什麼／承諾什麼／明確不管什麼 | **契約卡**（職責／前置條件／保證／明確不管） | [component-contracts.md](component-contracts.md) |
| 核心會停下來等人處理的狀況與怎麼恢復 | 診斷包（**diag**）、恢復手冊 | `aos7-diag` 唯讀列出判不出的槽 |
| 核心的行數上限，超過測試就紅 | **行數預算**（總行 2800／程式 2200） | `tests/core/test_budget.py` |

## 包

| 白話說法 | 正式名稱 | 一個例子 |
|---|---|---|
| 核心以外的可選擴充 | **模組包**（`modules/`，六個） | 工具、控制、子 daemon、once 保證、稽核、診斷 |
| 核心之上做「工作語意」的包 | **任務包**（`packs/`，三個） | step、budget、adapt |
| 包的三種接法：當任務、當包裝程式、當工具 | 接法 A／B／C | adapt 是任務；subd 是包裝程式；ctl 是工具 |
| 重啟＝先加一項釘在原槽的 once、再砍舊的 | 控制包（**control**）的 restart／reload | `aos7-ctl restart` |
| 走失但從沒跑過的一次性任務，補跑一次 | once 保證包（**once_retry**）、`retry_lost` | 當一個 keep 任務跑 |
| 每個 tock 把「上一次」抄一份留下來 | **歷史 module**（`history.py`） | `<node>/history/<id>.jsonl`，取樣的、會漏 |
| 照步驟表一步步派子工作 | **step 包**、直譯器、步驟表（`steps.json`）、框架（`frame.json`） | CSV→JSON→統計報表 |
| 子工作寫在槽外的成果紀錄 | **結果檔**（`results/<步>/<嘗試>.json`） | 槽刪了結果還在 |
| 等一件事等幾回合算到期 | **耐性**（patience）、本地回合 | 等 3 回合沒結果就停下 |
| 使用權：誰可以在什麼期限內用多少 | **grant**（budget 包） | `grant.json`，固定內容 |
| 只有一個寫者的帳本：可用、在途、已用 | **ledger**（帳） | 可用＋在途＋已用＝初始額度 |
| 用資源的唯一入口，先預留再執行再結算 | **gateway**（入口）、reserve→run→settle | 假 API 受理次數 |
| 同一筆業務的鍵，重播不重扣 | 業務鍵 K＝(預算, 持有人, 請求) | step 重送同一步不會扣兩次 |
| 把鄰居 node 的最新值換算成自己要的格式 | **adapt 包**、換算鏈（select／scale／threshold） | 溫度感測 → 風扇 |
| adapt 的輸出檔：值＋狀態（ok／不知道／沒有）＋依據版本＋出處 | **三態暫存器**（`in/<sense>.json`）、`basis`、`src` | 來源讀不到先撐舊值，到期翻不知道 |
| 把 LLM 當作者或當換算步驟的包（還沒做） | adapt-llm、LLM 作者 | 10-05 提案 |
| 替任務做決策的那一層（還沒做） | **kernel** 任務包 | 10-05 提案：決策骨架＋進度監督 |
| 專挑設計承諾打的對抗測試員（另一個 AI） | **astra**（codex） | 每輪一份報告，一輪一列在 [play/README.md](play/README.md) |
| 一輪「找問題→藍圖→修→驗收」 | **loop**（loop4～loop7） | [blueprint-loop6.md](blueprint-loop6.md) |
