# proto2 — 從零重來的 aos

← [AGENTS](../AGENTS.md)

## 這是什麼

一支 Python 腳本 `aos`，只做一件事：

```
aos exec <path>
```

- `<path>` 是**檔案** → 直接執行它，工作目錄＝檔案所在的資料夾。
- `<path>` 是**資料夾** → 讀 `<path>/.aos/insts.json`，照順序跑，工作目錄＝那個資料夾。

stdin/stdout/stderr 直接沿用，退出碼原樣傳回來。資料夾模式中間哪一條非 0 就停在那裡、回同一個碼。

## 為什麼另起爐灶

見 [reflections.md](../wf/workflows/ideas/reflections.md)：邊緣狀況想太早了，先把最小的那句話做出來。

## insts.json 長什麼樣

一個陣列，每一項是一條命令的 argv 陣列：

```json
[
  ["echo", "第一條"],
  ["pwd"]
]
```

## 怎麼玩

```sh
proto2/aos exec proto2/examples/hello.sh
proto2/aos exec proto2/examples/folder
bash proto2/test.sh
```

## 目前刻意不做

鎖、崩潰恢復、fsync、並發、逾時、重試、狀態檔、LLM、daemon、其他子命令、任何旗標。撞到再說。
