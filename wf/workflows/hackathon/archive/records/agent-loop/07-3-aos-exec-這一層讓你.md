← [在 `aos exec` 上做一條會動的 agent loop](../agent-loop.md)（分檔 7/24）｜所在：第 1 輪紀錄 ＞ 5. 題目那四個問題｜[上一份](06-2-真模型跑不跑得起來哪一支以及.md)｜[下一份](08-6-仍然不知道的.md)

#### ③ `aos exec` 這一層讓你手寫了幾次同樣的東西

| 該收掉的東西 | 幾位報 | 重寫情形 |
|---|---|---|
| 投遞（temp+rename ＋防碰撞檔名） | 4 | 每位一支 12–13 行，被 3–4 處呼叫 |
| 「下一批 instruction」的 JSON 字面 | 4 | 每位 2–3 份，有的兩種語言 |
| `aos status --json`／loop 的停止條件 | 3 | sentinel 檢查各處重寫 |
| `stdout`／`stderr`／`exit` 三件套的路徑 | 3 | 七站管線 39 次、其他每筆 instruction 抄一遍 |
| prompt／context 組裝（`emit-context`） | 3 | 兩處 header 格式要手動保持一致，容易打錯 |
| exit 傳播（前一筆非零就別跑我） | 2 | 腳本內各寫防禦；批次裡沒地方寫 |
| 每支 CLI 的 adapter（抽最後一則＋取 session id） | 2 | 每換一支 CLI 新寫一次 |
| 相位 journal／in-flight 租約 | 1 | 手寫 `phase.calling`／`phase.called` |
| 整套復原（`aos recover`） | 1 | `recover.sh` 從零手寫 |

各人提的方向：

- 排序 `deliver` > `status --json`（含停止條件）> 回合模板 > exit 傳播 > emit-context（p1）。
- `deliver` 不急（13 行），最該收的是 pipeline stage 檔名的生成：寫 `ctx | mdl | ...`，aos 自己配 `run/*.out|err|exit`（p2）。
- 抽最後一則、取 session id 是廠商差異，收不成子命令，能收成一份 adapter 契約＋各家設定（p4）。
- `aos exec` 在 fork 之前落盤 running marker（附子行程 pid）；`aos recover` 必須內建「孤兒還活著就拒絕」（p3）。

#### ④ tool call 那一段最痛的是什麼

轉換次數各人切法不同（8、8、10、13 次），**最痛的位置一致：模型講的參數變成 argv 的那一次轉換**——它同時是型別轉換與安全邊界，失敗時 loop 安靜地死掉。

- **型別錯在投遞後才被擋，loop 靜默死亡。** 模型送 `{"path":123}` → 投遞出 `"argv":["/usr/bin/wc","-w",123]` → 下一回合 `FieldTypeMismatch`、隔離成 `.bad`、`aos exec` 仍回 0 → loop 停住。warning 進 stderr，模型永遠不知道參數被拒。**在投遞前擋＝錯誤餵回模型、loop 自癒；在投遞後擋＝靜默死亡。這條線就是 `aos agent` 該站的位置。**
- **安全邊界只有字串。** 見[坑的總表](02-2-坑的總表/03-兩位獨立地都撞到.md)的 `/usr/bin/id`。模型輸出用空白拆參數，兩個參數以上就要自己發明引號規則。
- **佔位符撞名。** instruction 沒有 shell，`write_file(path, text)` 得寫成 `["/bin/sh","-c","printf '%s\\n' \"$2\" > \"$1\"","sh","$1","$2"]`：模板佔位符 `$1`／`$2` 與 sh 的位置參數長得一樣，取代函式只能認 `re.fullmatch(r"\$(\d+)", slot)` 才不會炸。任何需要 redirect、pipe、glob 的工具都會碰到。
- **回程沒有型別。** 工具結果變成塞進 prompt 的純文字；codex 沒有原生 tool-call 事件給外層用，只能借「最後一則訊息＋output-schema」假裝成 tool call。
- **工具結果拆成三個自己命名的檔**，沒有 correlation id、沒有交易邊界；exit 檔是「十進位字串加 LF」，要 `tr -d '\n'`。

不痛的一步：模型自由文字轉 JSON。codex 3 次真呼叫都乾淨輸出一行 JSON，`--output-schema` 讓這步消失；例外是 claude 會包圍籬。
