# inst（`aos_inst.py`）

← [proto8/lib](README.md)｜上一份：[指示詞](directives.md)｜下一份：[loop](loop.md)

設定從 TARGET／stdin／旗標來 → 用指示詞 lib 解好 → 挑認得的 key（其他忽略）→ 跑一次 → stdout 吐一份結果。照 NORMS N-12 重做（10-14）。

```
python3 proto8/lib/aos_inst.py [--key 值 ...] [TARGET | -] [-- argv...]
```

- 設定從哪來（`aos_cli`，D-1～D-3）：TARGET＝`.json` 檔，或資料夾（找 `.aos/inst.json`，沒有再找 `inst.json`），後面可接 `#/位置`（見[指示詞](directives.md)）；`-`＝從 stdin 讀（JSON 串流只看第一份，其餘 stderr 警告）；兩個都沒給＝`{}`。給 TARGET 就不讀 stdin。
- 旗標：純量 key 都有同名旗標（`--timeout-ms 100`、`--cwd-mkdir true`、`--id x`…，每個都要帶值，值先當 JSON 解、解不了當字串），蓋過檔或 stdin；`envs` 這種物件不鏡射。`--` 後面整段蓋過 `argv`。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。`cwd` 沒寫＝呼叫者的 cwd；`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`、`timeout_ms`（沒寫＝不限）、`grace_ms`（沒寫＝2000）、`id`（選填字串），加上布林的 `cwd_mkdir`、`envs_clear`、`*_inherit`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。
- 設定從 stdin 來時 `stdin_inherit`＝Conflict（stdin 已經被設定用掉，D-5）；`stdout_inherit`／`stderr_inherit` 照收，但子程式的輸出會混進 aos_inst 自己的 JSON 串流。
- **結果**（stdout＝返回值）：一份 `{"id", "code", "signal", "timed_out", "pid", "ms", "exit_file"}`。`code`＝子程式的碼（被訊號停掉＝128＋N，同 exit 檔）、`signal`＝訊號號碼或 null、`timed_out`＝被 `timeout_ms` 收掉、`id`＝設定的 `id`＞TARGET 的 id＞null。
- `run(x)`：x＝TARGET 或一份設定 dict（D-4，基準＝呼叫者的 cwd），回同一份結果 dict。aos_inst 自己出錯丟 `InstError`；命令列在 stderr 吐 `{"error": {"code", "msg"}}`，退出碼參考 127＝找不到程式、126＝不能執行、125＝其他（`exit_code(err)`）。子程式回幾號、被限時收掉都算正常做完（退出碼 0）。
- `exit` **選填**（與舊時代的橋樑，不是窗；暫定 e、[N-30](../NORMS/06-實作細則-N29至N34.md)）：要子程式的碼讀 stdout 那份結果的 `code`（tasks、loop 都這樣）。寫了就照寫：自己結束＝它的碼，被訊號停掉＝128＋N；沒起來不寫；寫不進去不管。`read_exit(path)` 讀最後一行（過渡用）。inst 不開 state／ctl 窗。
- 子程式留在 aos_inst 的行程群組。在主執行緒（命令列就是）收到 SIGINT／SIGTERM／SIGHUP 不死、轉給子程式，過 `grace_ms` 還沒結束就 SIGKILL，照樣寫 exit。要從外面停它、連孫程式一起清，是啟動它的人的事（aos_loop 把它起在新 session、整群收）。
- API：`find(target)`、`load(target)`、`parse(doc, base_dir, ident, at=(), piped=False)`、`run(x)`、`read_exit(path)`、`exit_code(err)`、`main(argv)`、`FLAGS`。
