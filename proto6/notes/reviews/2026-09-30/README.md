# 2026-09-30 spec／notes 審稿（第十七批之後）

← [筆記索引](../../README.md)｜[第十八批方向](../../verdicts/09-special-computing-os.md)

**這是審稿紀錄，不代表其中建議已採納。** 要不要改、怎麼改，由使用者逐條裁定。

## 怎麼審的

兩輪、都唯讀：

1. **Fable**（Claude，開六隊平行加一隊專審設計）照[審稿說明](brief.md)審 `proto6/notes/`（不含封存）與 `proto6/spec/`，交出 [Fable 報告](fable-report.md)，79 條。
2. **astra**（codex gpt-6-astra，唯讀沙盒）先獨立審一遍，再逐條回原文核對 Fable 的 79 條，另列 Fable 漏掉的，交出 [astra 報告](astra-report.md)。

範圍中途擴大兩次（說明檔已含）：使用者要求「審」也包括設計原則（冗餘、沒考慮到的狀況），並給了兩個檢查視角——「分配單位是一次計算」與「多層多 kernel」，見[第十八批](../../verdicts/09-special-computing-os.md)。

自動檢查兩邊都跑過：57 份 schema、205 份範例全過；`check_ids.py` 只找到兩個死條號，都在 notes。第十六、十七批的裁定都找得到落點，舊說法沒殘留。

## 合併結果

已抽到 [items.json](items.json)（87 列）。欄位：

- `id`：Fable 的編號（必-／設-／建-／裁-），astra 新找的加「新」字。
- `source`：fable 或 astra。
- `category`：必修、設計問題、建議、要使用者裁定。
- `title`：一句話標題，細節回各自報告找同編號。
- `astra_verdict`、`astra_reason`：astra 對 Fable 條目的核對（成立／部分成立／不成立），astra 自己的條目留空。
- `status`：處理狀態。
- `batch18`：依第十八批重新分類——直接修、已不成問題、改成各kernel自定、要使用者裁定。
- `plan`：一兩句怎麼處理；要裁定的列選項。

統計：Fable 79 條經 astra 核對，成立 19、部分成立 50、不成立 10；astra 另找 8 條（必修 4、設計 1、建議 1、裁定 2）。扣掉不成立的，**77 條待處理**。

兩邊公認最嚴重的：

- 多 UID 部署下 node 的 cgroup 框交不出去，每任務一層 cgroup 開不起來（必-1）。
- 投件內容就是完整執行設定，有投件權就能借對方身分跑任意程式（裁-1，astra 認為最嚴重）。
- 資源任務一失敗，收結果與取消也跟著被跳過（新必-1）。
- 兩個 daemon 可能同時管、互相清殺同一棵 cgroup 樹（新必-3）。

## 下一步

已依第十八批分類（見 `batch18` 欄）：直接修 42、要使用者裁定 28（合併成 20 題）、改成各 kernel 自定 6、已不成問題 1。接著逐題問使用者。

## 落 spec 之後

- 六隊改寫的交接紀錄：[team-handoffs.md](team-handoffs.md)（含各隊標「暫定」的疑點）。
- astra 唯讀核對：[astra-verify-report.md](astra-verify-report.md)。大部分已落，15 項問題：沒落乾淨 4、方案 A 殘留 9 組（協議篇仍有大量行為規則）、新矛盾 2。
- 同日另有第十九批（[tick 的最小核心](../../verdicts/10-tick-minimal-core.md)），會再改動 tick、收件與 cgroup 相關條文。
- 第十九批落 spec：[改寫計畫](batch19-plan.md)、[落點表](batch19-map.json)、[各隊交接](batch19-handoffs.md)（含標「暫定」的疑點）。
- astra 核對第十九批：[astra-b19-verify-report.md](astra-b19-verify-report.md)（14 項）。
- 第二十批：[改寫計畫](batch20-plan.md)、[落點表](batch20-map.json)。
