# compact 記憶整理包：把舊紀錄換成摘要，未完成項留下

compact 看工作資料夾裡的記憶檔，太長時先把舊原文封存，再換成一則摘要。最近 5 則和未完成的項目原樣留下。摘要按每件事（每封信）列出做了什麼，人和 AI 都讀得懂。

← [modules](../README.md)｜進階（全部指令、設定、AI 摘要、常駐、契約卡）→ [ADVANCED.md](ADVANCED.md)

## 先懂這四個詞

1. **node**：一個工作資料夾。
2. **記憶檔與「則」**：預設看 `notes/journal.jsonl`（一行一則）、`wf/SESSION-LOG.md` 和 `wf/handoffs/<日期>/STATE.md`（一個 `- ` 項目一則）。
3. **open 項**：還沒做完的（jsonl 有 `"open": true`，md 是 `- [ ]`），永遠不摘。
4. **archive**：被摘掉或忘掉的原文都原樣存在 `<node>/compact/archive/`，可逐字找回。

## 第一次跑（約 1 分鐘）

整段照抄（第一行先切到 repo 根）：造一個示範 node、看計畫、實際整理。

```sh
cd "$(git rev-parse --show-toplevel)"
N="$(mktemp -d)"; P="$(pwd)/proto7-2"
python3 "$P/modules/compact/examples/make_demo.py" "$N"
python3 "$P/modules/compact/aos7-compact" now "$N" --dry-run
python3 "$P/modules/compact/aos7-compact" now "$N"
```

預期看到這三行（`<node>`、`<job>` 每次不同；`now` 最後另印一行 JSON 給程式讀，可以不看）：

```text
已造好 <node>/notes/journal.jsonl：200 則舊紀錄＋20 則 open
notes/journal.jsonl：220 則，open 20，會摘掉 200 則（原因：大小超過 2048）
notes/journal.jsonl：220 則 → 21 則（摘掉 200、open 20 全留），102580 → 2023 bytes，原文在 compact/archive/<job>.jsonl（原因：大小超過 2048）
```

dry-run 和實跑印的是同一個原因：示範檔超過 2048 bytes，所以 `now` 自己就會整理（門檻可改，見 ADVANCED.md）。再跑一次 `now` 會說「不需要整理」。舊原文一字不缺在 `$N/compact/archive/`。

21 則＝20 則 open 原樣留著＋1 則新摘要（最近 5 則剛好都是 open）。看摘要：`head -c 300 "$N/notes/journal.jsonl"`。`<job>` 是這次整理的編號，也就是 archive 的檔名。

## 想做更多

日常只要 `now`。想親手刪掉某幾則，用 `forget`（例：`python3 "$P/modules/compact/aos7-compact" forget "$N" --file notes/journal.jsonl --from 1 --to 1 --dry-run`，先看再刪）；改門檻、讓 aos 每回合自動整理，見 [ADVANCED.md](ADVANCED.md)。測試：`python3 proto7-2/tests/run_all.py modules/compact/tests -v`。
