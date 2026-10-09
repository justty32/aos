← [proto7-2](README.md)

# 第一次用：一個指令起一個會做事的 AI

```text
 你 ──ask '一句話'──▶ ┌信箱┐ ──信──▶ ┌─ node：AI 住的資料夾 ─────────────┐
 你 ◀──回信／status── └────┘ ◀─回信─ │ 工作簿 wf/（停在哪、下一步，做完就刪）│
                                      │ 技能 skills/（一本一個資料夾）        │
       ┌心跳┐ 每秒叫醒 node 一次 ───▶ │ 醒來：看信→翻簿→挑技能→問 AI→回信    │
       └────┘（aos7-up 起的，Ctrl-C 停）└──────────────────────────────────────┘
```

## 5 個詞

| 詞 | 白話 |
|---|---|
| node | AI 住的資料夾 |
| 心跳 | 第 1 個指令開著時，每秒叫醒 node 一次 |
| 工作簿 | node 的 `wf/`：AI 記下停在哪、下一步；事做完就刪 |
| 信 | 要它做事就寄信，它辦完回信 |
| 技能 | node 的 `skills/`，AI 自己挑 |

## 3 個指令

每開一個新的終端機視窗，都先 `cd` 進 aos 專案資料夾（裡面有 `AGENTS.md`），再打這行：`alias aos7-up="python3 $PWD/proto7-2/modules/up/aos7-up"`

```sh
aos7-up /tmp/aos/bob                          # 1. 起一個叫 bob 的 node（資料夾會自己建）；開著別關，要停在這個視窗按 Ctrl-C
aos7-up ask /tmp/aos/bob '用一句話介紹你自己'   # 2. 另開一個終端機：寄信給 bob，等回信
aos7-up status /tmp/aos/bob                   # 3. 看 bob 現在怎樣
```

## 會看到什麼

1. 先一行「bob 起好了」，之後每秒一行心跳；寄信後多一行「收到信 → 問 AI → 已回信」。
2. bob 的回信全文（最多等 60 秒；沒等到就用第 3 個指令看）。預設是假 AI（不連網、不花錢，回固定句子）；第一次用假的就好；以後要真 AI，第 1 個指令後面加 `--model 模型名`。
3. 五行，一行一件：心跳活著沒／幾封信沒回／工作簿還有幾件事／幾本技能／AI 問了幾次、用了多少字。

到這裡就會了，可以停。

## 想多做一件事

| 想做 | 去看 |
|---|---|
| 改 AI 每次讀什麼 | [prompt](packs/prompt/README.md) |
| 信箱進階 | [mail](modules/mail/README.md) |
| 定時做事 | [routines](modules/routines/README.md) |
| 整理變厚的工作簿 | [compact](modules/compact/README.md) |
| 加技能 | [skills](modules/skills/README.md) |
| 看發生過什麼 | [events](modules/events/README.md) |
| 量 AI 用量 | [metrics](modules/metrics/README.md) |
| 讓 AI 寫小工具 | [author](packs/author/README.md) |
