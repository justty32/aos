# proto2 — 從零重來的 aos

← [AGENTS](../AGENTS.md)

## aos-exec：跑一個路徑

`aos-exec <path>`——**檔案**→直接執行，工作目錄＝檔案所在資料夾，退出碼原樣傳
回；**資料夾**→讀 `<path>/.aos-inst`（純文字），整段原樣丟給 `os.system()` 跑，
工作目錄＝那個資料夾，不解析、不拆行、沒有批次指令。找不到路徑，或資料夾沒有
`.aos-inst`：印一句錯誤到 stderr，退出碼 2。

## aos-loop：反覆跑 aos-exec

`aos-loop [dir] [--steps N] [--interval SEC] [--stop-when-empty]`。`dir` 省略
就用目前目錄。每一步：讀 `.aos-inst`（不存在＝空字串）、**立刻清空**、再把內容
丟給 `os.system()` 跑（去頭尾空白後是空的就不跑）。命令想留下一步，就在自己跑
的時候把新內容寫回 `.aos-inst`，下一圈會撿到。

- `--steps N`：跑幾步就停（退出碼 0）；不給就無限跑。
- `--interval SEC`：每步之間睡幾秒，預設 1。
- `--stop-when-empty`：讀到空的就以 0 退出；不給的話空的那步不跑、照樣算一步繼續。

命令退出碼不影響迴圈，但每步結束印一行到 stderr，例如 `aos-loop: step 2 exit 5`。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先做最小的那句話。

## 怎麼玩

```sh
proto2/aos-exec proto2/examples/hello.sh
proto2/aos-loop proto2/examples/loop --stop-when-empty --interval 0
bash proto2/test.sh
```

## 目前刻意不做

鎖、崩潰恢復、fsync、並發、逾時、重試、狀態檔、LLM、daemon、其他子命令、
批次結構（.aos-inst 就是一段 shell，不是資料）。撞到再說。
