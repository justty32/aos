# tool cpu payload 與結果（第 1 版）

← [proto5 README](../README.md)｜共用格式：[cpu-queue](cpu-queue.md)｜程式：[aos-tool-cpu](aos-tool-cpu.md)

> 這份是 proto5.1 做出來的版本（2026-09-22 回流，照 [23 題拍板](../notes/2026-09-22-decisions.md)）。**proto5 的程式還沒照這份實作**；能跑的實作在 [proto5.1/lib](../../proto5.1/lib/README.md)。

CPU 身分 `_type`＝`tool_cpu`、版本 1。資料夾、info、共同 result 欄位、短鎖與收屍見共用規範。

## 1. 請求 payload

```text
{"inst": <aos_inst.load_obj 解好的 dict>,
 "stdin": "<tool call arguments 字串>", "timeout_ms": 60000,
 "result": "/absolute/agent/tool-results/0.json"}
```

inst／stdin／timeout_ms 都必填。inst 是 **load_obj 的回傳形狀去掉 stdin／stdout**，不是原始 inst JSON：
包含 argv、絕對 cwd、cwd_mkdir、envs／envs_clear、以及帶 path／選項布林的 stderr／exit。
agent 交件前去掉 inst.stdin／inst.stdout；CPU 不讀、不驗也不採用這兩格，參數與輸出由管線接管。
CPU 驗執行所需形狀：argv 非空字串陣列且 argv[0] 非空；cwd／非空串流 path 必須是絕對路徑，
串流選項為布林，envs 為合法環境字串表；供 OS 使用的字串不得含 NUL。stdin 是 arguments 原字串，
timeout_ms 是字面正整數，bool 不算。空串流 path 沿用 load_obj 的「沒寫」表示法。

CPU 不解析指示詞、不讀 agent 設定或工具檔。argv 的命令名可沿既有 exec 規則用 PATH 查找，
argv 中一般參數也不會被當成路徑重寫。`$env` 在 agent 解好，但 **envs_clear=false 仍繼承 CPU
執行時的環境與 PATH**，這包請求不是完整環境快照；有此需要時由工具明寫 envs／clear。

合法共同欄位下，payload 格式壞掉會認領、發布 BadPayload 並搬 done，tick 回 0。
壞 JSON、頂層非物件、非法 result 無法安全回覆，依共用規範搬 bad、繼續下一份，tick 回 1。

## 2. 結果

```json
{"ok":true,"code":0,"kind":"child","timed_out":false,"stdout":"輸出"}
```

ok:true 表示已得到 run_inst 的執行結果，**不是 code 必為 0**：kind 為 `child` 或 `aos`，
code 為退出碼／aos 失敗碼；timed_out 取真實逾時旗標，不用 exit 143 猜測。stdout 是捕獲的
UTF-8 文字（非法位元組替換），逾時仍保留已收到輸出。inst 的 stdin／stdout 由管線接管，
stderr／exit／cwd／envs 按既有 aos_exec 規則。

失敗固定 `{"ok":false,"code":"代號","msg":"白話"}`。壞 payload 用 BadPayload，
執行建立請求時的 ValueError／OSError 用 EngineFailed。
這些是已知失敗；工具的逾時與非零退出也已有執行結果，不算結果不明。

收屍／失聯固定為 `{"ok":false,"code":"Reaped","msg":"結果不明：工具可能已經跑了，也可能沒有"}`。
running 超過收屍期限還沒有結果，就無法知道崩在認領後、工具執行中，還是工具已完成而未發布結果；
原程序也可能仍在跑。這幾種都算結果不明，不重試、不推測副作用。agent 交給模型的 tool content
仍是 `{"ok":false,"error":"結果不明：工具可能已經跑了，也可能沒有"}` 的 JSON 字串，
由 agent 看 code=Reaped 轉成這個固定文字，不加工具名稱或其他前綴。結果沒有 name／id。
