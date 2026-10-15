# inst（`aos_inst.py`）

← [proto8/lib](README.md)｜下一份：[loop](loop.md)

設定從 TARGET／stdin／旗標來 → 解好指示詞 → 挑認得的 key（其他忽略）→ 跑一次 → stdout 吐一份結果。

```
python3 proto8/lib/aos_inst.py [--key 值 ...] [TARGET | -] [-- argv...]
```

- 設定從哪來（`aos_cli`，N-21～N-24）：TARGET＝`.json` 檔，或資料夾（找 `$AOS_DIRNAME/inst.json`（環境變數，沒設＝`.aos`，空字串＝資料夾本身；不合法＝`DirnameBad`，N-35），沒有再找 `inst.json`），後面可接 `#/位置`（N-35，寫法在 `aos_cli.py` 檔頭）；`-`＝從 stdin 讀（一份；多份＝`InputExtra` 錯、退非 0）；兩個都沒給＝`{}`。給 TARGET 就不讀 stdin。
- 旗標：純量 key 都有同名旗標（`--timeout-ms 100`、`--cwd-mkdir true`、`--id x`…，每個都要帶值，值先當 JSON 解、解不了當字串），蓋過檔或 stdin；`envs` 這種物件不鏡射。`--` 後面整段蓋過 `argv`。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。`cwd` 沒寫＝呼叫者的 cwd；`stdin`／`stdout`／`stderr` 的相對路徑從解出來的 `cwd` 算。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`timeout_ms`（沒寫＝不限）、`grace_ms`（沒寫＝2000）、`id`（選填字串），加上布林的 `cwd_mkdir`、`envs_clear`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。沒寫的串流接 `/dev/null`；要接呼叫者的就寫 `/dev/stdin`／`/dev/stdout`／`/dev/stderr`（三個 `*_inherit` 布林與 exit 檔 10-15 深夜 KISS 批次 1 拿掉，[彙整](../thinking/2026-10-15-kiss/README.md) 1.1、1.2）。`stderr` 寫成 `/dev/stderr` 時 stderr 上的東西是子程式的、不是 aos_inst 的，aos_inst 正常做完照樣退 0（不違反 N-43）。
- **結果**（stdout＝返回值）：一份 `{"id", "code", "signal", "timed_out", "pid", "ms"}`。`code`＝子程式的碼（資料，照實轉交子程式的；被訊號停掉＝128＋N）、`signal`＝訊號號碼或 null、`timed_out`＝被 `timeout_ms` 收掉、`id`＝設定的 `id`＞TARGET 的 id＞null。
- `run(x)`：x＝TARGET 或一份設定 dict（N-25，基準＝呼叫者的 cwd），回同一份結果 dict。aos_inst 自己出錯丟 `InstError`；命令列在 stderr 吐 `{"error": {"code", "msg"}}`、退出 1（是哪種錯看 `code`）。子程式回幾號、被限時收掉都算正常做完（退出碼 0）。inst 不開 state／ctl 窗。
- 子程式留在 aos_inst 的行程群組。在主執行緒（命令列就是）收到 SIGINT／SIGTERM／SIGHUP 不死、轉給子程式，過 `grace_ms` 還沒結束就 SIGKILL。要從外面停它、連孫程式一起清，是啟動它的人的事（aos_loop 把它起在新 session、整群收）。
- API：`find(target)`、`load(target)`、`parse(doc, base_dir, ident, at=())`、`run(x)`、`main(argv)`、`FLAGS`。
