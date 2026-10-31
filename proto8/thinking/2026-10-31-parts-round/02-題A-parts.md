← [入口](../2026-10-31-parts-round.md)｜涵蓋：題 A 結論｜上一份 [01-契約核對](01-契約核對.md)｜下一份 [03-題B-round](03-題B-round.md)

## 題 A 結論：parts 退成「aos-exec 格式的約定」＋ `which`／`run` 薄殼

使用者問（10-31 傍晚）：「aos parts 是否可以用 aos exec 和 ref,env 以及其他一些東西組出來？」答：**可以，而且大半本來就是 aos-exec 的東西**。

### 逐項對照（parts 現在做的 → 誰已經能做）

| parts 做的事 | aos-exec 已能 | symlink＋`.env` 能 | 只有 parts 程式能 |
|---|---|---|---|
| 名字→路徑（集中表） | ✔ 一份 JSON、每槽一個 key，`aos-exec parts.json#/槽`（C-72、N-62；實跑 A、K、L） | ✔ `<agent>/<槽>` 捷徑或真資料夾（實跑 F） | — |
| 每槽帶 env | ✔ 槽寫成物件、`.env` key（實跑 A、L） | ✔ 真資料夾放 `.env`、`_entry` 捷徑指 lib（實跑 F；整格捷徑就沒地方放） | — |
| env 值用 `$env`／`$ref` | ✔ `.env` key 的值可放指示詞（實跑 A 的 `$ref`） | ✘ `.env` 檔只展開 `${名字}`（N-59） | — |
| 相對路徑從註冊檔算、搬家不斷 | ✔ 字串轉向從寫著它的檔算（N-61） | ✔ 相對捷徑 | — |
| 跑 | ✔ 就是 aos-exec | ✔ | — |
| 改（add／rm／ls／get） | ✔ `aos-json set／del／get`（parts 現在也是叫它寫） | `ln`／`rm` | add 先驗目標跑得動——aos-exec 跑時照樣會報，提前驗是便利 |
| 查而不跑（印路徑、解開的 env） | 半：`aos-json get --resolve 檔#/槽/.env`（實跑 N） | `readlink` | `which --json` 一次給路徑＋env＋來源 |
| 「註冊檔沒寫＝固定名字」順序、「沒掛」退 10 | ✘ 找不到一律 `EntryMissing` 退 1（實跑 E） | ✘ | ✔ **parts 唯一的本體** |
| env 蓋過環境 | ✘ 預設不蓋（N-58；實跑 C1），要蓋那一跳加 `--dotenv-override`（C2） | 同左 | ✔ 現在 `run` 與 roundlib 都蓋（代定 4） |

所以 parts 的本體只剩兩件：查找順序＋沒掛判定；其餘是 aos-exec 的能力穿了另一件外衣。使用者 10-31 早說 parts「相比 symlink，多了可以用 $env/$ref 指定東西」——**這個能力是 aos-exec 的 `.env` key（C-72、N-59 第 4 件），不是 parts 的**；`parts.json` 現在的 `{"path", "env"}` 是把 `{"_entry", ".env"}` 重寫一次（C-48 不新增格式、C-56 最後減法都該清）。

### 結論（照原則代定、可翻案）

1. **格式退成 aos-exec 的格式（約定）**：`parts.json` 每槽的值就是 aos-exec 認得的值——字串＝純指向（等於 symlink）、`{".env": {…}, "_entry": "路徑"}`＝帶 env 的指向；`endpoint/<名>`、`hook/<點>` 變巢狀物件；頂層不再包 `"parts"` 一層，整份檔就是槽表，`aos-exec <agent>/parts.json#/<槽> <agent> …` 直接可跑。這落在使用者 10-31 早「指令用法，json 格式啥的還需要微調」的範圍。agent-nia 的樣子：
   ```json
   {"queue": "../../lib/agent/queue", "history": "../../lib/agent/history", "act": "../../lib/agent/act",
    "hook": {"pre_think": {".env": {"AOS_COMPACT_MAX_BYTES": "65536"}, "_entry": "../../lib/agent/compact"}},
    "endpoint": {"default": "../../lib/endpoint/fake",
                 "litellm": {".env": {"AOS_BRAIN_URL": "http://localhost:4000/v1", "AOS_BRAIN_MODEL": "chatgpt-gpt-6-luna-low"},
                             "_entry": "../../lib/endpoint/openai"}}}
   ```
   （`round` 槽消失：`AOS_ROUND_ON_EMPTY` 改走 argv，見 [03](03-題B-round.md) 與實作計畫 A3。）
2. **`aos-parts` 縮成薄殼，只留 `which [--json] 槽` 與 `run 槽 [args…]`**（約 80 行）：查找順序照決定 16（註冊檔→固定名字→退 10）只寫在這裡（C-52）；`run`＝找到就 `exec aos-exec 目標 args…`、不自己疊 env——env 由 aos-exec 讀 `.env` key 處理。`add／rm／ls／get` 刪掉，改 `aos-json set／del／get`（README 寫對照表）；add 的提前驗證交給跑的時候報（C-52 不替下層驗、C-53 入口默認正常）。
3. **env 的語意改口：預設不蓋（N-58）**，取代 10-28 代定 4「註冊檔的 env 蓋過環境」。理由：N-58 是使用者 10-22 定的；兩套語意會讓 `aos-exec parts.json#/x` 與 `aos-parts run x` 行為不同（C-56 寫什麼就做什麼）。要蓋的呼叫者在自己那一跳寫 `--dotenv-override`（`aos-parts run` 原樣轉給 aos-exec）。影響：`test_aos_parts::test_run_env_args_code`、`test_round_endpoint::test_via_parts_registry_env` 改斷言；roundlib 不再自己 `env.update`。
4. **器官怎麼叫**：roundlib／queue／compact／act 改成 `which` 問有沒有、再 `aos-exec <agent>/parts.json#/<槽>`（註冊的）或 `aos-exec <agent>/<槽>`（固定名字），env 一律交給 aos-exec。`candidates()` 的 endpoint 候選＝`parts.json#/endpoint` 的 key 聯集 `<agent>/endpoint/` 底下的名字。
5. **層級**：parts 不再是「一支與 fsm 平級的標準庫程式」，而是「agent 資料夾的一個約定（檔名 `parts.json`、aos-exec 格式）＋一支查找薄殼」——跟 C-74 10-31 加註字面相撞，列成 [衝突 1](04-匯流與衝突.md#衝突)，條文不自己改。
