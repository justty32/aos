# 任務書：aos-exec 普通檔案目標收 `-- args`（使用者 2026-09-13 同意；compact 後派）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。只准改 `proto4-3/aos_exec.py`、`aos_run.py`、`test/test_targets.py`、`test/test_run.py`、`README.md`、`docs/exec.md`、`docs/run.md`，以及 `proto4-4/src/aos.janet`＋`test/aos.janet`＋`README.md`、`proto4-6/aos_py.py`、`lua/aos.lua`、對應測試與 README。不要 commit／push、不開 agent。開工前三邊測試先跑一次確認綠（proto4-3 220、proto4-4 38/12/45、proto4-6 65）。

背景：inst 慣例裡「普通檔案目標＝直接執行它、不帶參數」，`aos/llm`（Janet）與 `llm_submit`（三語言）都因此繞路寫短命 inst.json 或直接 subprocess。使用者同意：**普通檔案目標可以在 `--` 之後帶參數**。

定案：
- `aos-exec FILE [--stderr …] [--timeout-ms N] -- a b c`：`--` 之後全部原樣當 argv[1:]；**只對普通檔案目標有效**，`.json`／資料夾目標給了 `--` → 用法錯（2），訊息說「inst 目標的參數寫在 inst.json 的 argv 裡」。`run_target(..., args=None)`。
- `aos-run` 原樣轉傳。
- `aos/call`（Janet）新 opt `:args [...]`；Python `aos.call(target, args=[...])`；Lua `opts.args`。只對普通檔案目標有效，其他目標給了就 error。
- 把 `aos/llm`、`llm_submit`（三語言）改成用 `args` 直接叫 `aos-llm`／`aos-kernel`，拆掉短命 inst 與 subprocess 繞路；行為與既有測試不變。
- 測試每邊至少 3 條；文件：exec.md「三種目標」那段、README「怎麼跑」加一行、proto4-4／proto4-6 README 的 `args` 一句。
- 回報八行。
