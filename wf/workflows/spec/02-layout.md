# 02 版面：`.aos/` 裡有什麼
← [入口](README.md)

一個裡面有 `.aos/` 的資料夾就是一塊地。頂層是人的，`.aos/` 是機器的。這份檔規定 `.aos/` 底下有哪些路徑、誰能寫、何時長出來、進不進 git、算不算世界的記憶。

## 一塊地是什麼

- **S-02-01** 一塊地必須是一個裡面有 `.aos/` 的資料夾；沒有 `.aos/` 的資料夾禁止被當成地來跑。〔裁決 2026-09-03〕
- **S-02-02** 頂層必須留給人：人寫的原稿、資料、子資料夾都放頂層。〔裁決 2026-09-03〕
- **S-02-03** 機器產的東西必須全部住在 `.aos/`；人禁止手改 `.aos/` 裡的檔，只准透過 `aos` 子命令碰。〔裁決 2026-09-03〕
- **S-02-04** 新增一個檔必須當成定義一個名字（檔案＝名字＋內容），資料夾結構就是作用域與壽命。〔預設 2026-09-05，B-01〕
- **S-02-05** 家（`$AOS_HOME`，預設 `~`）必須也是一塊地，只是它的 `.aos/` 多幾樣東西。〔主編補〕

## 看得到哪裡、身分、生死

- **S-02-06** 一塊地只看得到自己地盤上的東西；要看外面必須靠掛載或 symlink 明白開洞。〔裁決 2026-09-04〕
- **S-02-07** 禁止把「看得到哪裡」當成權限；准不准做是門房那層的事，見 [13](13-doorman-l1.md)。〔裁決 2026-09-03〕
- **S-02-08** 路徑必須是一塊地的唯一身分；禁止另外發一組 id 給地。〔裁決 2026-09-04〕
- **S-02-09** 資料夾被刪掉必須當成這塊地死了；行程還活著就是孤魂，必須先停掉再清登記。〔裁決 2026-09-04〕
- **S-02-10** 搬家必須當成原地死掉、新位置生一個新的；禁止做搬家通知。〔裁決 2026-09-04〕
- **S-02-11** `aos mv`（停時鐘＋搬＋重新登記）必須是唯一正確的搬法，細節見 [08](08-daemon.md)；直接 `mv` 的後果由 daemon 巡邏兜底。〔預設 2026-09-05，C-04〕
- **S-02-12** 登記表與呼叫記錄必須記真實路徑（realpath），禁止記 symlink 路徑。〔主編補〕

## 版面總表（相對於一塊地的根）

- **S-02-13** `.aos/` 底下每條路徑必須恰有一個 writer，就是下表那一欄；禁止兩支程式寫同一條路徑。例外只有明列的這四樣：狀態檔（子的 run、daemon、LLM 世界，或父的 exec 代寫）、停止原因檔（exec、run、daemon）、登記表（exec 登 `pending`、`run --register`、門房、daemon，全走 `registry.lock`）、`.aos/lock`（誰拿到誰寫）。〔主編補〕
- **S-02-14** 下表的路徑名必須照抄，禁止各地自己改名或加層。〔主編補〕

| 路徑 | 是什麼 | 寫 | 讀 | 何時建 | git | 記憶 |
|---|---|---|---|---|---|---|
| `*.aos.json`（頂層） | 原稿，`main.aos.json` 是入口 | 人／LLM | 編譯器 | 人建 | 是 | 是 |
| `agent.json`（頂層） | agent 限制參數，只有 agent 有 | 人 | agent 的圈 | `aos agent init` | 是 | 是 |
| `.gitignore`（頂層） | `aos init` 產的片段 | `aos init` | git | init | 是 | 是 |
| `.aos/layout.json` | 版面版本 | `aos init` | 全部子命令 | init | 是 | 是 |
| `.aos/config.json` | 世界層設定 | `aos config` | exec／run | init | 是 | 是 |
| `.aos/tools/<名>.json` | 工具登記表，一工具一檔 | `aos tool add` | agent | 加工具時 | 是 | 是 |
| `.aos/contacts.json` | 通訊錄 | `aos contact add` | `aos say` | 加聯絡人時 | 是 | 是 |
| `.aos/program.tmp/` | 編譯中的暫存目錄，成功才改名成 `program/` | 載入器 | 載入器 | 開始編譯時 | 否 | 否 |
| `.aos/program/<模板名>.json` | 編譯器吐的模板 | 載入器 | exec | 被點名開那刻 | 否 | 否 |
| `.aos/series.json` | 接力棒 | exec | exec、`aos status` | 第一次被開 | 否 | 否 |
| `.aos/inbox/` | 收件匣 | 投遞者 | exec | init | 否 | 否 |
| `.aos/inbox/rejected/` | 隔離起來的無效投遞 | exec | 人 | 第一次隔離 | 否 | 否 |
| `.aos/control/` | 控制收件匣 | `aos stop` 等 | run | init | 否 | 否 |
| `.aos/control/done/` | 處理過的控制信 | run | 人 | 第一次處理控制信 | 否 | 否 |
| `.aos/mail/` | exec 從收件匣搬來的信 | exec | 地上的程式 | 第一次搬信 | 否 | 否 |
| `.aos/mail/read/` | agent 讀過的信 | agent 的圈 | 人 | 第一次讀信 | 否 | 否 |
| `.aos/ticks/<N>/started` | exec 開跑那一格的記號 | exec | exec | 那一格開頭 | 否 | 否 |
| `.aos/ticks/<N>/insts/<inst id>.json` | 第 N 格要跑的指令 | exec | exec | 那一格開頭 | 否 | 否 |
| `.aos/ticks/<N>/results/<inst id>.json` | 那筆指令跑起來沒有 | exec | exec | 指令跑完 | 否 | 否 |
| `.aos/ticks/<N>/tmp/<inst id>/` | 暫存目錄，指令跑完就刪 | exec | 該筆指令 | 起指令前 | 否 | 否 |
| `.aos/ticks/<N>.crashed/` | `aos fix` 丟棄的現場 | `aos fix` | 人 | `aos fix` 丟現場時 | 否 | 否 |
| `.aos/frames/<串 id>/` | 堆疊框，串跑完由 exec 刪 | exec | 該條串 | 串開跑 | 否 | 否 |
| `.aos/calls/<call id>.json` | 呼叫記錄 | exec | 父、`aos status` | 開子地時 | 否 | 否 |
| `<結果落點>.status.json` | 狀態檔，壞了才有 | 子地的 run；子被殺時 daemon 補寫（唯一的雙 writer 例外，見 [07](07-call-and-delivery.md)） | 父的 `await` | 失敗那一刻 | 否 | 否 |
| `<結果落點>.usage.json` | 那筆 LLM 請求用掉多少 | LLM 世界 | 父、agent | 回覆寫完 | 否 | 否 |
| `.aos/units.json` | 處理單元表，只有 LLM 世界有，含 `api_key_env` 名稱 | daemon | LLM 世界的圈 | daemon 起它時 | 絕不 | 否 |
| `.aos/requests/<request id>.json` | 一筆 LLM 請求的處理紀錄，只有 LLM 世界有 | LLM 世界 | LLM 世界、`aos status` | 收到請求時 | 否 | 否 |
| `.aos/usage.json` | agent 累計用量，只有 agent 有 | agent 的圈 | agent 的圈 | 第一圈跑完 | 否 | 是 |
| `.aos/stopped.json` | 停止原因檔 | exec（串失敗）／run（開跑先刪、停時必寫）／daemon（`--kill` 後代寫） | 人 | run 停下時 | 否 | 否 |
| `.aos/errors.log` | jsonl，寄件人解析不出的投遞這類雜錯 | exec | 人 | 第一次出錯 | 否 | 否 |
| `.aos/lock` | 獨佔建檔的鎖，內容 `{"pid","pid_start"}`；持有者死了可以收回 | exec／run | exec／run | 開跑時 | 否 | 否 |

家（`$AOS_HOME`）的 `.aos/` 多這幾樣：

| 路徑 | 是什麼 | 寫 | 讀 | 何時建 | git | 記憶 |
|---|---|---|---|---|---|---|
| `.aos/config.json` | 使用者層設定（含 `units`） | `aos config` | daemon、`aos llm` | init | 是 | 是 |
| `.aos/registry.json` | 登記表 | 四方，見 [08](08-daemon.md) | 全部子命令 | daemon 首次起 | 否 | 否 |
| `.aos/registry.lock` | 登記表的鎖 | daemon | daemon | 首次改登記表 | 否 | 否 |
| `.aos/daemon.pid` | daemon 的行程編號 | daemon | `aos daemon` | daemon 起 | 否 | 否 |
| `.aos/ledger.jsonl` | 帳簿，一次 LLM 呼叫一行 | LLM 世界 | 人 | 第一次呼叫 | 否 | 是 |
| `.aos/ask/` | `aos llm ask` 的 prompt 與結果 | `aos llm ask` | 人 | 第一次 ask | 否 | 否 |
| `.aos/doorman.log` | 門房看到的動靜 | 門房 | 人 | 門房起 | 否 | 否 |
| `.aos/llm/` | LLM 世界，它自己是一塊地 | 見上表 | 見上表 | `aos daemon start` 或 `aos llm init` 發現不在時 `aos init` 它 | 是 | 是 |

- **S-02-15** 是不是世界記憶必須用這一句判：把這個檔刪掉，世界的意思會不會變。只會變快變慢的是機器暫存。〔主編補〕
- **S-02-16** 機器暫存禁止進 git；行程編號檔存進版本裡，回滾後系統會以為早就不在的行程還活著。〔主編補〕
- **S-02-17** 「記憶」與「進 git」必須當兩欄看：帳簿是記憶但會一直長，所以不進 git。〔主編補〕
- **S-02-18** `.gitignore` 政策必須是一份全域規範，`aos init` 產出片段；一塊地禁止自己決定 `.aos/` 裡哪些進 git。〔預設 2026-09-05，C-05〕
- **S-02-19** 工具登記表與通訊錄必須留在 `.aos/`，人只透過 `aos tool`／`aos contact` 寫；是靜態設定，進 git。〔主編補〕
- **S-02-20** 存檔、回滾、複製重跑必須用 git 做，禁止 aos 自己發明一套版本邊界。〔裁決 2026-08-28〕

## 兩個版本欄

- **S-02-21** 版面版本必須放 `.aos/layout.json` 的 `layout_version`（整數，第一版 `1`）。〔預設 2026-09-05，L-04〕
- **S-02-22** 每份頂層 json 必須有自己的 `format_version`（整數，第一版 `1`）；版面版本與格式版本是兩件事。〔預設 2026-09-05，L-04〕
- **S-02-23** 讀到不認得的欄位必須拒絕；要擴充只准放在具名的 `ext` 物件裡。〔裁決 2026-08-28〕

子地怎麼開、設定檔的欄位、「記憶就是地」，還有版本不合／地 id／誕生／tmpfs 那幾條，都在 [02b 版面補充規則](02b-layout-rules.md)。

## 範例

`.aos/layout.json`：

```json
{
  "format_version": 1,
  "layout_version": 1,
  "land_id": "9f2c1ab34d5e6f708192a3b4c5d6e7f8",
  "ext": { "moved_from": "/home/me/old/place" }
}
```

## 待使用者拍板

- S-02-04 檔案＝名字＋內容，新增檔案就是定義一個名字。〔預設，B-01〕
- S-02-05 家也是一塊地。〔主編補〕
- S-02-11 `aos mv` 是唯一正確的搬法。〔預設，C-04〕
- S-02-12 只記 realpath，不記 symlink。〔主編補〕
- S-02-13 每條路徑恰一個 writer。〔主編補〕
- S-02-14 路徑名照抄，不准各地改名。〔主編補〕
- S-02-15 世界記憶的判別式：刪了意思會不會變。〔主編補〕
- S-02-16 機器暫存不進 git。〔主編補〕
- S-02-17 「記憶」與「進 git」是兩欄；帳簿是記憶但不進 git。〔主編補〕
- S-02-18 `.gitignore` 一份全域規範，`aos init` 產片段。〔預設，C-05〕
- S-02-19 工具登記表與通訊錄留在 `.aos/`，人只透過子命令寫。〔主編補〕
- S-02-21 版面版本放 `.aos/layout.json`。〔預設，L-04〕
- S-02-22 各 json 各有 `format_version`。〔預設，L-04〕
- 矛盾：登記表裡的時鐘規格像世界記憶（刪了那塊地就永遠不會自己走），但同一份檔裝著行程編號這種暫存。我選「整份 `registry.json` 算暫存、不進 git」，因為回滾一份含行程編號的檔會讓 daemon 認錯活人；代價是重開機後時鐘要由父或使用者重新登記。

## 現況對照

今天的 `.aos/` 裡是 `inbox/`、`batch/<N>/`、`every/`、`state.json`，沒有 `layout.json`、`series.json`、`program/`、`calls/`、`frames/`、`ticks/`，也沒有版面版本欄與地 id。人寫的東西跟機器暫存混住，頂層與 `.aos/` 的分工沒做。`.gitignore` 是排掉整個 `.aos/` 再開幾個洞，不是 `aos init` 產的片段。
