← [proto7-2](README.md)

# 第一次用：一個指令起一個會做事的 AI

```text
 你 ─ask 寄信─▶ ┌ node：AI 住的資料夾 ───────────┐
 你 ◀─回信───── │ 工作簿 wf/：停在哪、下一步     │
 心跳：每秒 ──▶ │ 技能 skills/：AI 自己挑        │
 叫醒 node 一次 │ 醒來：看信→問 AI→回信→記簿子  │
                └────────────────────────────────┘
```

| 詞 | 白話 |
|---|---|
| node | AI 住的資料夾 |
| 心跳 | 指令 1 開著時，每秒叫醒 node 一次 |
| 工作簿 | node 的 `wf/`：AI 記下停在哪、下一步；事做完就刪 |
| 信 | 要它做事就寄信，它辦完回信 |
| 技能 | node 的 `skills/`，AI 自己挑 |

## 3 個指令

每開一個視窗，先 `cd` 進 aos 資料夾（有 `AGENTS.md` 那層）再打：`alias aos7-up="python3 $PWD/proto7-2/modules/up/aos7-up"`

```sh
aos7-up /tmp/aos/bob                          # 1. 起 bob；開著別關，停＝按 Ctrl-C
aos7-up ask /tmp/aos/bob '用一句話介紹你自己'   # 2. 另開視窗 2：寄信給 bob，等回信（≤60 秒）
aos7-up status /tmp/aos/bob                   # 3. 看 bob 現在怎樣
```

## 會看到什麼（實跑）

視窗 1（數字每次不同；Ctrl-C 後印最後一行）：

```text
bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI（要真的加 --model）
另開一個終端機問它：aos7-up ask /tmp/aos/bob '一句話'
看狀態：aos7-up status /tmp/aos/bob　停：Ctrl-C
心跳 4
心跳 5 收到 1 封信
心跳 6 → 問 AI → 已回信
心跳停了；檔案都留著，再跑 aos7-up /tmp/aos/bob 就接上
```

指令 2（預設假 AI：不連網、不花錢、照抄你的信）：

```text
bob 回信（DONE）：（假 AI）收到你的信：用一句話介紹你自己
```

指令 3：

```text
心跳：活著，第 5 下
信：未讀 0 封（要回 0 封）；你的信箱有 0 封回信
工作簿：還有 0 件事沒做完；停在：- 16:51 回了 you-20261009T165125-4e36ba603228；體檢 OK
技能：3 本
AI：假 AI；問過 1 次，用了 1102 token
檔案：/tmp/aos/bob、/tmp/aos/you（全清：先停心跳，再刪這兩個資料夾）
```

DONE＝辦完了；token＝AI 讀寫的字量。`--model` 與 `--help` 裡的 `-d`、`stop` 第一次用不到。

## 收掉

視窗 1 按 Ctrl-C（心跳停，檔案留著）；不要了就 `rm -r /tmp/aos`，整個刪（含藏起來的 `.aosd`）。

到這裡就會了。細節 → [up](modules/up/README.md)。

## 想多做一件事

改 AI 每次讀什麼 [prompt](packs/prompt/README.md)｜信箱進階 [mail](modules/mail/README.md)｜定時做事 [routines](modules/routines/README.md)｜整理變厚的工作簿 [compact](modules/compact/README.md)｜加技能 [skills](modules/skills/README.md)｜看發生過什麼 [events](modules/events/README.md)｜量 AI 用量 [metrics](modules/metrics/README.md)｜讓 AI 寫小工具 [author](packs/author/README.md)
