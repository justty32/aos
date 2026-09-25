# 唯讀審查任務：commons（跨團隊公共資料夾＋圖書館員）

你是唯讀審查員。不要改任何檔、不要跑會寫檔的指令。用中文白話回報。

## 看什麼

規格：`proto5/spec/team/commons.md`。程式：`proto5/lib/aos_team_commons.py`（主體）、`proto5/lib/aos_agent_init.py`（`_access` 的 commons 掛載、`_ensure_commons`、`_commons_tools`、`_make_commons`）、`proto5/lib/aos_team_format.py`（`validate_roster` 的 commons 鍵、`member_may` 加 `contribute`、`RESERVED_MOUNTS`）、`proto5/lib/aos_team.py`（`member_context`、`cmd_init` 建 commons、`BadCommons`）、`proto5/lib/aos_team_post.py`（`run` 裡叫 `post_round`）、`proto5/lib/aos_team_requests.py`（兩個新 kind）。工具：`proto5/tools/task/commons_search`、`commons_submit`、`commons_verdict`。模板：`proto5/templates/librarian/`。測試：`proto5/lib/test/test_team_commons.py`。
背景：`proto5/spec/team/wall.md`、`layout.md`、`spawn.md`（同一套申請→郵差→處理函式的模式）。

## 重點找

1. **牆**：成員（含圖書館員模型）有沒有任何路能寫進 commons 館藏（`lessons/`、`teams/`…、`index.json`），或讓郵差替它寫到 commons 以外／別隊的地方？`on_contribute` 抄附件：realpath、符號連結、TOCTOU、硬連結、大小上限、檔名（投稿號、slug）能不能穿越？
2. **只有圖書館員能判**：`commons_write` 的權限、`NotAsked`／`AlreadyDone`、冪等、跨圖書館員隊（`judge.json` 的 team）。
3. **崩潰與冪等**：`on_contribute`（staging → rename → 紀錄）、`desk`（judge.json → notice）、`pending_results`（寫 status 與 notice 的先後）、`ingest`（寫檔與 index 的先後）崩在中間會怎樣？會不會漏回信、重複入庫、index 與檔對不上？
4. **名冊三層**：預設開、團隊關、成員蓋過、重跑 init 補掛／拿掉，有沒有對不上（例：關了但工具還在、郵差還准 `contribute`）？
5. **執行位規則**（只准 `#!` 開頭的有執行位）、「完全重複」與「像」的判法有沒有明顯漏洞。
6. `aos-team commons import` 對 `proto5/playbook` 的解析、以來源為準「換新」會不會誤刪別的條目。

## 回報格式

- **必修**（會出事的 bug 或牆的洞）：每條＝檔:行、怎麼觸發、建議修法。
- **建議**（可以更好）：同上，簡短。
- **不用修**：你看了覺得沒問題的重點，一行一個。
