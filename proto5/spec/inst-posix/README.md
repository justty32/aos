← [spec 總導航](../README.md)

# inst.json 規範：`posix` 呼叫（第 1 版）

← [proto5 README](../../README.md)｜規範先行；實作：[lib/aos_directives.py](../../lib/aos_directives.py)（指示詞）、
[lib/aos_inst.py](../../lib/aos_inst.py)（讀、驗，第 1～5 節）、[lib/aos_exec.py](../../lib/aos_exec.py)（執行，第 6 節；
命令列說明在 [aos-exec.md](../aos-exec/README.md)）；proto4-3 的 [aos_inst.py](../../../proto4-3/aos_inst.py)／
[aos_exec.py](../../../proto4-3/aos_exec.py) 是凍結的舊版參考（`$ref` 帶 `#位置`、位置＝實體路徑那幾條沒跟上）

這份文件把「一份 inst.json 到底長什麼樣、怎麼解讀」寫成規範。規範先行：程式照本文做；程式跟
本文對不上、又不是本文寫錯的地方，回來改本文。

一句話：**一份 inst.json 就是「叫作業系統跑一個程式」那一句話的 JSON 版**——跑什麼（`argv`）、
在哪跑（`cwd`）、三條串流接哪（`stdin`／`stdout`／`stderr`）、結束碼寫哪（`exit`）、環境變數
（`envs`）。沒有 shell、沒有管線、沒有萬用字元，就是一次 `execve`。

---

## 7. 這份規範沒管的事

- **怎麼反覆跑、多久跑一次**：那是 cpu（aos-run）與 kernel 的事，inst 只描述「一次」。
- **退出碼的約定語意**（100＝做完、101＝在等）：那是 kernel 跟程式之間的約定，不是 inst 格式
  的一部分。
- **`_type` 不是 `posix` 的 inst**：各自另寫規範。

## 各節

| 檔 | 內容 |
|---|---|
| [metainfo.md](metainfo.md) | §1 `_metainfo`：這份 inst 是哪一種、第幾版 |
| [fields.md](fields.md) | §2 整體形狀；§3 七個欄位：§3.1 路徑以 `cwd` 為中心、§3.2 `envs` 兩種寫法、§3.4 沒有 shell |
| [opt.md](opt.md) | §3.3 `$opt` 選項物件 |
| [directives.md](directives.md) | §4 指示詞：任何值的位置都能放；§4.1 幾個容易踩的 |
| [errors.md](errors.md) | §5 錯誤代號（讀／驗階段） |
| [exec.md](exec.md) | §6 執行語意（執行者要做到的） |
