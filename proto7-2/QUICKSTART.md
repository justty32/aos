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
| node | AI 住的資料夾；下面的 `bob` 就是一個 node（名字你取） |
| 心跳 | 指令 1 開著時，每秒叫醒 node 一次 |
| 工作簿 | node 的 `wf/`：AI 自己記做到哪；事做完就刪 |
| 信 | 要它做事就寄信，它辦完回信 |
| 技能 | node 的 `skills/`，AI 自己挑 |
| 假 AI | 預設的 AI：不連網、不花錢，照抄你的信回你 |

## 3 個指令

每開一個視窗，先 `cd` 進 aos 資料夾（git clone 下來、有 `AGENTS.md` 的那個）再打：`alias aos7-up="python3 $PWD/proto7-2/modules/up/aos7-up"`

```sh
aos7-up /tmp/aos/bob                          # 1. 起 bob；開著別關，停＝按 Ctrl-C
aos7-up ask /tmp/aos/bob '用一句話介紹你自己'   # 2. 另開視窗 2：寄信給 bob，等回信（≤60 秒）
aos7-up status /tmp/aos/bob                   # 3. 看 bob 現在怎樣
```

## 會看到什麼

視窗 1（數字每次不同；Ctrl-C 後印最後一行）：

```text
bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI
另開一個終端機問它：aos7-up ask /tmp/aos/bob '一句話'
看狀態：aos7-up status /tmp/aos/bob　停：Ctrl-C
心跳 4
心跳 5 收到 1 封信
心跳 6 → 問 AI → 已回信
心跳停了；檔案都留著，再跑 aos7-up /tmp/aos/bob 就接上
```

指令 2：

```text
bob 回信：（假 AI）收到你的信：用一句話介紹你自己
```

指令 3：

```text
心跳：活著
信：bob 一共收到 1 封，回了 1 封；你的信箱有 0 封回信還沒看
工作簿：最後記下：回了「用一句話介紹你自己」
技能：3 本（AI 自己挑來用）
AI：假 AI（不連網、不花錢，照抄你的信回你）；問過 1 次
要收掉：先在視窗 1 按 Ctrl-C 停心跳，再刪掉整個資料夾：rm -r /tmp/aos
```

## 卡住時

問 AI 問到一半被打斷（例如電腦當了），指令 3 的「信」那行會有「正在辦 1 封」，下面多一行：

```text
卡住了：「幫我寫一首短詩」問 AI 時被打斷，不知道 AI 回了沒；不用動手，約 60 秒後 bob 會寄信給你
```

不用動手：60 秒後 bob 寄一封「說卡住了」的信到你的信箱（`cat /tmp/aos/you/inbox/*.md` 看），接著辦下一封。想重來就把那封再寄一次（假 AI 不花錢）。

## 收掉

照指令 3 最後一行「要收掉」做。

到這裡就會了。細節 → [up](modules/up/README.md)。

## 想多做一件事

改 AI 每次讀什麼 [prompt](packs/prompt/README.md)｜信箱進階 [mail](modules/mail/README.md)｜定時做事 [routines](modules/routines/README.md)｜整理變厚的工作簿 [compact](modules/compact/README.md)｜加技能 [skills](modules/skills/README.md)｜看發生過什麼 [events](modules/events/README.md)｜量 AI 用量 [metrics](modules/metrics/README.md)｜讓 AI 寫小工具 [author](packs/author/README.md)
