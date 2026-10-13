# inst（`aos_inst.py`）

← [proto8/lib](README.md)｜上一份：[指示詞](directives.md)｜下一份：[loop](loop.md)

讀一份 JSON → 用指示詞 lib 解好 → 挑認得的 key（其他忽略）→ 跑一次。

```
python3 proto8/lib/aos_inst.py TARGET
```

- TARGET：`.json` 檔，或資料夾（找 `.aos/inst.json`，沒有再找 `inst.json`），後面可接 `#/位置`（見[指示詞](directives.md)）。`find()` 回 id（realpath，有位置就接 `#/位置`）。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。`cwd` 沒寫＝呼叫者的 cwd；`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`、`timeout_ms`（沒寫＝不限）、`grace_ms`（沒寫＝2000），加上布林的 `cwd_mkdir`、`envs_clear`、`*_inherit`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。
- `run(target)`：跟命令列一模一樣。正常做完回 None（命令列 0），子程式回幾號、被限時收掉都算正常做完；aos_inst 自己出錯丟 `InstError`（命令列印「代號: 白話」，參考 127＝找不到程式、126＝不能執行、125＝其他，`exit_code(err)`）。
- 子程式的碼只寫進 `exit` 檔：自己結束＝它的碼，被訊號停掉＝128＋N；沒起來不寫；寫不進去不管。`read_exit(path)` 讀最後一行（給 loop、tasks 用）。
- 子程式留在 aos_inst 的行程群組。在主執行緒（命令列就是）收到 SIGINT／SIGTERM／SIGHUP 不死、轉給子程式，過 `grace_ms` 還沒結束就 SIGKILL，照樣寫 exit。要從外面停它、連孫程式一起清，是啟動它的人的事（aos_loop 把它起在新 session、整群收）。
- API：`find(target)`、`load(target)`、`parse(doc, base_dir, ident, at=())`、`run(target)`、`read_exit(path)`、`exit_code(err)`。
