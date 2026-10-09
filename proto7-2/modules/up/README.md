← [modules](../README.md)｜[QUICKSTART](../../QUICKSTART.md)

**這是什麼**：一個指令起一個會收信、問 AI、回信的 node。
**一行跑起來**：`aos7-up /tmp/aos/bob`
**看到什麼**：`bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI（要真的加 --model）`

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
bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI（要真的加 --model）
另開一個終端機問它：aos7-up ask /tmp/aos/bob '一句話'
看狀態：aos7-up status /tmp/aos/bob　停：Ctrl-C
心跳 4
心跳 5 收到 1 封信
心跳 6 → 問 AI → 已回信
心跳停了；檔案都留著，再跑 aos7-up /tmp/aos/bob 就接上
```

另一個視窗的 ask 與 status：

```text
bob 回信（DONE）：（假 AI）收到你的信：用一句話介紹你自己
心跳：活著，第 5 下
信：未讀 0 封（其中待回 0 封）；你的信箱有 0 封回信
工作簿：open 0 項；停在：- 16:21 回了 you-20261009T162122-16c043c82df7；體檢 OK
技能：3 本
AI：假 AI；問過 1 次，用了 1104 token
檔案：/tmp/aos/bob、/tmp/aos/you（全清：先停心跳，再刪這兩個資料夾）
```

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [ADVANCED.md](ADVANCED.md)（給維護者，不用讀）
