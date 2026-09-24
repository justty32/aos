← [aos-exec](README.md)｜[spec 總導航](../README.md)

# 給程式用：`run_target()`

```python
import aos_exec
code, kind = aos_exec.run_target(xxx, dir_target=".aos/inst.json", timeout_ms=0,
                                 on_spawn=None, stderr=None, args=None)

r = aos_exec.run_target_full(xxx, ...)   # 同樣的參數，另有 on_target、on_poll、poll_ms
r.code, r.kind, r.timed_out, r.stopped, r.ms
```

- `run_target()` 只回 `(code, kind)`，不帶 `timed_out`。要知道是不是真的撞到期限（子程式收到 TERM 後自己以 0
  結束也算）、是不是被 `on_poll` 強停、跑了幾毫秒，用 `run_target_full()`：回 `code`／`kind`／`timed_out`／
  `stopped`／`ms`。`on_poll(p)` 每 `poll_ms` 毫秒被叫一次，回真值＝強停（只 TERM 該 process group，寬限後 KILL）。

- `on_spawn`：子行程一開起來就用那個 `Popen` 叫它一次、收完屍再用 `None` 叫一次（給呼叫者砍正在跑的那個用；
  命令列用不到）。
- `stderr`：同 `--stderr`（`None`＝照 inst.json、`"-"`＝繼承、字串＝路徑）。
- `args`：同 `--`（`None`＝沒給、陣列＝有給，含空陣列）。只對普通檔案有效。
- 反覆執行不是這支程式的事，是 kernel 的事（[kernel.md](../kernel/README.md)）。

# 例子

```sh
aos-exec                                # ＝ aos-exec .：跑 ./.aos/inst.json，base＝現在的資料夾
aos-exec ./job                          # 跑 ./job/.aos/inst.json，base＝./job
aos-exec ./job --dir-target other.json  # 改跑 ./job/other.json，base 還是 ./job
aos-exec ./one.json --timeout-ms 5000   # 單一 .json，base＝它所在的資料夾，5 秒上限
aos-exec ./job --stderr -               # 子程式的錯誤印出來看
aos-exec ./hello.sh -- a "b c" --x      # 普通檔案：直接跑，參數原樣接
echo $?                                 # 0＝子程式回 0；125＝aos-exec 自己失敗；2＝用法錯
```
