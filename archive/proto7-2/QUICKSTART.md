← [proto7-2](README.md)

# 第一次用：一個指令起一個會做事的 AI

node 每次被叫醒就：看信 → 問 AI → 回信給你 → 記進工作簿。

| 詞 | 白話 |
|---|---|
| node | AI 住的資料夾（不是程式）；下面的 `bob` 就是一個 node（名字你取） |
| 心跳 | 指令 1 開著時，每秒叫醒 node 一次（視窗 1 的數字＝第幾次） |
| 工作簿 | node 的 `wf/`：AI 記做到哪、下一步；指令 3 的「最後記下」＝最近一筆 |
| 信 | 要它做事就寄信，辦完回信到你的信箱 `/tmp/aos/you/inbox/`；還沒回＝正在辦 |
| 技能 | node 的 `skills/`：一本本做事說明，AI 自己挑來看 |
| 練習用的 AI | 預設的 AI：不連網、不花錢，照抄你的信回你 |

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
bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 練習用的 AI
另開一個終端機問它：aos7-up ask /tmp/aos/bob '一句話'
看狀態：aos7-up status /tmp/aos/bob　停：Ctrl-C
心跳 4
心跳 5 收到 1 封信
心跳 6 → 問 AI → 已回信
心跳停了；檔案都留著，再跑 aos7-up /tmp/aos/bob 就接上
```

指令 2：

```text
bob 回信：（練習用的 AI）收到你的信：用一句話介紹你自己
```

指令 3：

```text
心跳：活著
信：bob 一共收到 1 封，回了 1 封；你的信箱有 0 封回信還沒看
工作簿：最後記下：回了「用一句話介紹你自己」
技能：3 本（AI 自己挑來用）
AI：練習用的 AI（不連網、不花錢，照抄你的信回你）；bob 一共問過 AI 1 次
要收掉：先在視窗 1 按 Ctrl-C 停心跳，再刪掉整個資料夾：rm -r /tmp/aos
```

## 卡住時

問 AI 時被打斷（如當機），指令 3 會變這樣：

```text
信：bob 一共收到 2 封，回了 1 封、正在辦 1 封；你的信箱有 0 封回信還沒看
卡住了：「幫我寫一首短詩」問 AI 時被打斷，bob 不知道 AI 回了沒；不用動手，約 1 分鐘內 bob 會寄信給你
```

約 1 分鐘內 bob 寄一封說卡住的信給你（`cat /tmp/aos/you/inbox/*.md` 看），「信」那行變「回了 1 封、1 封卡住（已寄信說明）」，接著辦下一封。看完信二選一：不管它，或用指令 2 把同一句再寄一次（練習用的 AI 不花錢）。

收掉：照指令 3 最後一行做。細節 → [up](modules/up/README.md)。

## 想多做一件事

改 AI 每次讀什麼 [prompt](packs/prompt/README.md)｜信箱進階 [mail](modules/mail/README.md)｜定時做事 [routines](modules/routines/README.md)｜整理變厚的工作簿 [compact](modules/compact/README.md)｜加技能 [skills](modules/skills/README.md)｜看發生過什麼 [events](modules/events/README.md)｜量 AI 用量 [metrics](modules/metrics/README.md)｜讓 AI 寫小工具 [author](packs/author/README.md)
