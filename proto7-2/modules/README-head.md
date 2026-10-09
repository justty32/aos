← [modules](README.md)｜[QUICKSTART](../QUICKSTART.md)

# 包 README 的三行頭（模板）

包的 README 只放三樣：**三行頭、第一次跑、一行連到 ADVANCED.md**。進階、契約卡、規則、已知限制、測試，一律放同資料夾的 `ADVANCED.md`。新手的概念、指令只算 README。

```md
**這是什麼**：<一句白話，說它替 node 做什麼>
**一行跑起來**：`<在 aos7-up 起好的 node 上再打的一個指令>`
**看到什麼**：<這一行實際印出來的樣子>

## 第一次跑
<最多三個指令與預期輸出；沒有就刪這段>

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [ADVANCED.md](ADVANCED.md)（給維護者，不用讀）
```

規則：

1. README 不含代號（條號、隊名、spec 編號）與 QUICKSTART 五個詞以外的新詞；帳、回合、預留、ack、退出碼、daemon、tick 都不出現。
2. 不另起 daemon、不另開帳：第二行只在 `aos7-up /tmp/aos/bob` 起好的 node 上加一個指令。
3. 第二行要實跑過，第三行抄實際輸出（太長就抄第一行）。
4. 「完成了」那行之後，README 不再有別的內容；其餘全搬 ADVANCED.md。做法可照 [mail](mail/README.md)。

## 範例（up 包自己，全文見 [up/README.md](up/README.md)）

```md
**這是什麼**：一個指令起一個會收信、問 AI、回信的 node。
**一行跑起來**：`aos7-up /tmp/aos/bob`
**看到什麼**：`bob 起好了：工作簿 ✓ 信箱 ✓ 技能 3 本 ✓ 練習用的 AI（要真的加 --model）`

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [ADVANCED.md](ADVANCED.md)（給維護者，不用讀）
```
