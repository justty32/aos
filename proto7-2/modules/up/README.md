← [modules](../README.md)｜[QUICKSTART](../../QUICKSTART.md)

**這是什麼**：一個指令起一個會收信、問 AI、回信的 node。
**一行跑起來**：`aos7-up /tmp/aos/bob`
**看到什麼**：`bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI`

## 第一次跑

每開一個新的終端機視窗，都先 `cd` 進 aos 專案資料夾（裡面有 `AGENTS.md`），再打這行：`alias aos7-up="python3 $PWD/proto7-2/modules/up/aos7-up"`

```sh
aos7-up /tmp/aos/bob                          # 起 bob；開著別關，要停按 Ctrl-C
aos7-up ask /tmp/aos/bob '用一句話介紹你自己'   # 另開一個終端機：印 bob 的回信全文（最多等 60 秒）
aos7-up status /tmp/aos/bob                   # 看 bob 現在怎樣
```

工作簿＝bob 自己記『停在哪、下一步』的筆記（wf/），事做完就刪。

實跑輸出（2026-10-09，假 AI 不連網、不花錢）。第一個視窗：

```text
bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI
另開一個終端機問它：aos7-up ask /tmp/aos/bob '一句話'
看狀態：aos7-up status /tmp/aos/bob　停：Ctrl-C
心跳 4
心跳 5 收到 1 封信
心跳 6 → 問 AI → 已回信
心跳停了；檔案都留著，再跑 aos7-up /tmp/aos/bob 就接上
```

另一個視窗的 ask 與 status：

```text
bob 回信：（假 AI）收到你的信：用一句話介紹你自己
心跳：活著
信：bob 一共收到 1 封，回了 1 封；你的信箱有 0 封回信還沒看
工作簿：最後記下：回了「用一句話介紹你自己」
技能：3 本（AI 自己挑來用）
AI：假 AI（不連網、不花錢，照抄你的信回你）；bob 問過它 1 次
要收掉：先在視窗 1 按 Ctrl-C 停心跳，再刪掉整個資料夾：rm -r /tmp/aos
```

卡住時 status 多一行「卡住了：…不用動手，約 1 分鐘內 bob 會寄信給你」；從被打斷算起約 1 分鐘（真 AI 約 10 分鐘），說卡住的信寄到 `/tmp/aos/you/inbox/`，信那行變「回了 N 封、1 封卡住（已寄信說明）」。

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [ADVANCED.md](ADVANCED.md)（給維護者，不用讀）
