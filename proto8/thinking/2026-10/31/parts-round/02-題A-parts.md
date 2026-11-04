← [入口](README.md)｜涵蓋：題 A 結論｜上一份 [01-契約核對](01-契約核對.md)｜下一份 [03-題B-round](03-題B-round.md)

## 題 A 結論：parts 退成「aos-exec 格式的約定」

使用者問（10-31 傍晚）：「aos parts 是否可以用 aos exec 和 ref,env 以及其他一些東西組出來？」答：**可以，而且大半本來就是 aos-exec 的東西**。

### 逐項對照（parts 現在做的 → 誰已經能做）

名字→路徑、每槽帶 env、env 值用 `$env`／`$ref`、相對路徑從註冊檔算、跑、改（`aos-json set／del／get`），aos-exec 都已能（C-72、N-59 第 4 件、N-61、N-62；[01](01-契約核對.md) 實跑 A、K、L）。只有 parts 程式做得到的是「註冊檔沒寫＝看固定名字」的查找順序與「沒掛」判定（aos-exec 找不到一律 `EntryMissing` 退 1）。使用者 10-31 早說 parts「相比 symlink，多了可以用 $env/$ref 指定東西」——這個能力是 aos-exec 的 `.env` key，不是 parts 的。

### 結論（照原則代定、可翻案）

1. **格式＝aos-exec 的格式（約定）**：`parts.json` 每槽的值就是 aos-exec 認得的值——字串＝純指向（等於 symlink）、`{".env": {…}, "_entry": "路徑"}`＝帶 env 的指向；`endpoint/<名>`、`hook/<點>` 是巢狀物件；頂層不包 `"parts"` 一層，整份檔就是槽表，`aos-exec <agent>/parts.json#/<槽> <agent> …` 直接可跑。這落在使用者 10-31 早「指令用法，json 格式啥的還需要微調」的範圍。agent-nia 的樣子：
   ```json
   {"queue": "../../lib/agent/queue", "history": "../../lib/agent/history", "act": "../../lib/agent/act",
    "hook": {"pre_think": {".env": {"AOS_COMPACT_MAX_BYTES": "65536"}, "_entry": "../../lib/agent/compact"}},
    "endpoint": {"default": "../../lib/endpoint/fake",
                 "litellm": {".env": {"AOS_BRAIN_URL": "http://localhost:4000/v1", "AOS_BRAIN_MODEL": "chatgpt-gpt-6-luna-low"},
                             "_entry": "../../lib/endpoint/openai"}}}
   ```
   （沒有 `round` 槽：queue 空的停法走 argv `--on-empty`，見 [03](03-題B-round.md)。）
2. **`aos-parts` 整支刪、不留殼**（10-31 本題原結論是縮成 `which`／`run` 薄殼；11-01 已改：衝突 1 使用者「搞不好連薄殼都不用」，實作整支刪；找格放 `lib/agent/parts.py`，見 [05 做的時候](05-方向題與實作計畫.md#實作計畫)）；查找順序照決定 16（註冊檔→固定名字）只寫在一處（C-52）；shell 裡改用 `aos-json set／del／get`，對照表在 bin/README。
3. **env 預設不蓋（N-58）**，取代 10-28 代定 4「註冊檔的 env 蓋過環境」；要蓋的呼叫者在自己那一跳寫 `--dotenv-override`。
4. **器官怎麼叫**：問有沒有登記，再 `aos-exec <agent>/parts.json#/<槽>`（註冊的）或 `aos-exec <agent>/<槽>`（固定名字），env 一律交給 aos-exec。endpoint 候選＝`parts.json#/endpoint` 的 key 聯集 `<agent>/endpoint/` 底下的名字。
5. **層級**：parts 不是「與 fsm 平級的標準庫程式」，是 agent 資料夾的一個約定（檔名 `parts.json`、aos-exec 格式）——跟 C-74 10-31 加註字面相撞，列成 [衝突 1](04-匯流與衝突.md#衝突)（11-01 決定改口）。
