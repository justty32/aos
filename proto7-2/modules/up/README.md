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

第一個指令實跑輸出（假 AI 不連網、不花錢）：

```text
bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 假 AI（要真的加 --model）
另開一個終端機問它：aos7-up ask /tmp/aos/bob '一句話'
看狀態：aos7-up status /tmp/aos/bob　停：Ctrl-C
心跳 7
心跳 8
心跳停了；檔案都留著，再跑 aos7-up /tmp/aos/bob 就接上
```

ask 目前還沒裝；裝好後印 bob 的回信全文（最多等 60 秒）。停下後 status 實跑六行：

```text
心跳：停了（最後第 8 下）；起它：aos7-up /tmp/aos/bob
信：未讀 0 封（其中待回 0 封）；你的信箱有 0 封回信
工作簿：open 0 項；停在：（還沒記）；體檢 OK
技能：3 本
AI：假 AI；問過 0 次，用了 0 token
檔案：/tmp/aos/bob、/tmp/aos/you（全清：先停心跳，再刪這兩個資料夾）
```

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [ADVANCED.md](ADVANCED.md)（給維護者，不用讀）
