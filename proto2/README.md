# proto2 — 從零重來的 aos

← [AGENTS](../AGENTS.md)

## 這是什麼

一支 Python 腳本 `aos-exec`，只做一件事：

```
aos-exec <path>
```

- `<path>` 是**檔案** → 直接執行它，工作目錄＝檔案所在的資料夾，退出碼原樣傳回來。
- `<path>` 是**資料夾** → 讀 `<path>/.aos-inst`（純文字檔），把整個檔案內容原樣丟給
  `os.system()` 跑，工作目錄＝那個資料夾。**不解析、不拆行、沒有批次指令**——
  裡面就是你平常在終端機打的 shell 命令，愛寫幾行寫幾行。

找不到路徑，或資料夾裡沒有 `.aos-inst`：印一句錯誤到 stderr，退出碼 2。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先把最小的那句話做出來。
連「一個陣列的 argv」都嫌太結構化——改成整段丟 shell，更土、更好懂。

## .aos-inst 長什麼樣

```sh
echo 第一句
echo 第二句
pwd
```

## 怎麼玩

```sh
proto2/aos-exec proto2/examples/hello.sh
proto2/aos-exec proto2/examples/folder
bash proto2/test.sh
```

## 目前刻意不做

鎖、崩潰恢復、fsync、並發、逾時、重試、狀態檔、LLM、daemon、其他子命令、任何旗標、
批次結構（.aos-inst 就是一段 shell，不是資料）。撞到再說。
