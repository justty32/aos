# build-cycle — 動手之前的兩道閘門（spec → plan → do）

← [WORKFLOWS](../../WORKFLOWS.md)｜進度表 [roadmap](../roadmap.md)｜動手之後 [feature-dev](../feature-dev/README.md)

**這個工作流做什麼**：一件有份量的事**真的開始寫之前**，先過兩道**要使用者點頭**的閘門
——**規劃 spec**（要做成什麼樣、怎樣算做完）與**實作 plan**（怎麼做、動哪些檔、分幾步）。
兩個都點頭才動手；動手就**交棒 feature-dev**，本工作流不重複那邊的流程。

**什麼時候用**：roadmap 的一個階段（M0、M1…）、一個有份量的功能、一次結構搬遷。
**什麼時候不用**：單行 bug、文字修正、使用者當場口述的小事——那些直接走 feature-dev。

## 三個閘門

```
① spec ── 寫 spec.md ─→ 交使用者 ─→ 他點頭
             ↓ 不點頭：改 spec，重來（不准跳去 plan）
② plan ── 寫 plan.md ─→ 交使用者 ─→ 他點頭
             ↓ 不點頭：改 plan；若發現 spec 錯了，退回 ①
③ do   ── 交棒 feature-dev（改 → ctest 綠 → code map → 文檔 → commit）
             ↓ 完成
   收尾 ── spec.md/plan.md 整包移進 archive/，roadmap 與 SESSION-LOG 更新
```

**閘門是硬的**：沒點頭就不寫下一份、不碰程式。使用者說「這份我不看了，你直接做」＝他
放棄該閘門，記一行在該項目的 spec/plan 開頭，照樣往下走。

## 每個閘門的完成定義

| 閘門 | 產物 | 沒有這些就不算寫完 |
|---|---|---|
| ① spec | `spec.md` | **要做成什麼樣**（結果狀態，不是動作清單）／**驗收條件**（可機械檢查的那種）／**明確不做什麼**（防膨脹）／**先裁的決定**（動工前必須拍板的問題，逐條列）／動工前該讀哪些檔 |
| ② plan | `plan.md` | **步驟**（每步一個可停下的檢查點）／**動哪些檔**（逐檔，對照 [code map](../common/code-map.md)）／**每步怎麼驗**／**風險與退路**／若有外包：任務書給誰、驗收怎麼收 |
| ③ do | 程式碼／文件 ＋ 綠燈 | 照 [feature-dev](../feature-dev/README.md)：`cmake --build --preset default && ctest --preset default` 全綠、code map 同步、文檔補齊，才 commit |

**spec 只講「什麼」、plan 只講「怎麼」**——spec 裡出現檔名與步驟就是越界，那是 plan 的事。

## 產物放哪

```text
build-cycle/
    README.md              ← 本檔（工作流入口）
    <項目 slug>/           ← 一個項目一夾，slug 見下
        spec.md
        plan.md
    archive/               ← 做完的項目整夾移進來（長出來才建）
```

- **項目 slug**：roadmap 階段用 `m0-<一句話>`（如 `m0-legislation`）；其他用短 kebab-case。
- **做完就封存**：整夾移進 `archive/`，**不留現役夾、不拆**（[DEV-GUIDE](../../DEV-GUIDE.md)
  已定：已完成的 spec/plan 一律移 `archive/` 凍結，也不套單檔大小門檻）。
- 中途廢棄的項目一樣移進 `archive/`，在 `spec.md` 開頭補一行「**廢棄：原因**」。

## 跟別的工作流怎麼分

| 這個工作流 | 管什麼 | 分界 |
|---|---|---|
| **roadmap** | **哪一階段、先裁什麼**（進度表） | 它說「做 M0」，build-cycle 說「M0 怎麼跑」。階段推進後回頭更新 roadmap |
| **build-cycle**（本檔） | **動手之前**：spec、plan、兩道閘門 | 不碰程式碼，不重複驗證流程 |
| **feature-dev** | **動手之後**：改、驗證、文檔、commit | 閘門 ③ 直接交棒過去 |
| **ideas / workshop / hackathon** | 還在想、還沒決定要不要做 | 有結論才進 build-cycle；build-cycle 裡被迫下的新裁決要**記回** ideas 與 [verdicts](../ideas/verdicts.md) |

## 常備規則

1. **spec 之前先過既有裁決**：[verdicts A 表](../ideas/verdicts.md)（別重想已拍板的）與
   [call-format/keep](../ideas/call-format/keep.md)（別打掉優點）。
2. **實作中被迫下的新裁決＝正式裁決**：記回 ideas 對應檔 ＋ verdicts ＋（M0 之後）SPEC。
3. **spec 的「先裁」沒裁完也可以動工**，但**碰到那個決定的那一行就得停下來裁**，不准臨時湊合。
4. 跨 session 時在 [SESSION-LOG](../../SESSION-LOG.md) 留一行「`<項目>` 卡在閘門 ①/②/③」。
