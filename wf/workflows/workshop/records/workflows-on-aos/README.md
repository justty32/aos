# 用 aos 實現 workflows

← [workshop](../../README.md)｜前情：[核心行程與子行程](../core-process-and-subprocess.md)／[四個懸而未決的選擇](../four-open-choices-tradeoffs.md)／[agent loop](../agent-loop-architecture.md)／[回頭審視](../step-back-review.md)／[隨意發想](../free-ideation.md)

| | |
|---|---|
| **主題** | 如何用 aos 實現 workflows 那樣的功能 |
| **開場** | 2026-08-25 |
| **已跑輪數** | 一輪 |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與〈四個懸而未決的設計選擇〉〈agent loop〉〈回頭審視〉〈隨意發想〉是同一批人**（同一批 codex session 續下來） |

## 先讀這段（500 字懶人包）

這輪第一次知道 aos 的目的：改善純 markdown 的 workflows。**四位共同方向是：markdown 繼續保存
「怎麼想、為什麼」；aos 只接手「現在輪到誰、卡在哪、何時再醒、下一步投去哪」。**候選動作是
`wf start／wait／resume／done／status`；inbox 仍是信，只有 `accept` 後才變成工作。

但這還不能直接開做。四位都只是**推論**出兩種痛：open-only／歸檔靠記憶，以及模板安裝、升級
靠手工合併；使用者尚未說真正哪裡不好用。另一個 4／4 未決問題是活狀態要不要隨 Git 跨機：
若要，通常不版控的 `.aos` 不能當唯一真源。

最先該問的是：最近一次具體卡在哪？只能消掉一步，會選安裝升級、找路由、維護狀態、記得 tick，
還是 agent 不照流程？

---

使用者在這輪第一次揭露 aos 的起點：

> 其實 **aos 在最初，只是我覺得 `C:/code/mine/workflows` 不是很好用，才想出來的規劃**。
> 開啟下一輪吧，大家一起想想看，**如何用 aos 實現 workflows 那樣的功能**。

這改變了整個專案的座標。前面幾輪的 CPU 類比、行程、lane、kernel、agent loop 都是可能的
**手段**；這輪第一次看見它們原本想服務的**目的**。

`workflows` 本身沒有 executor：`WORKFLOWS.md` 用自然語言派發意圖，各工作流 README 解釋理由、
判準與步驟；`SESSION-LOG.md`、`WAIT_USER.md`、`inbox/` 靠人或 agent 手動維護。它的分層原則是
「每層只指向下一層」，也有一套非侵入式匯入方法。這個 repo 的 `wf/` 同時是它用了幾個月的
活實例，已經長出 workshop、ideas、tick 等 template 原先沒有的東西。

但是使用者只說「不是很好用」，**沒有說痛在哪裡**。所以下面凡是談目前痛點，都標成四位從
template 與活實例推出的假說，不寫成使用者已確認的事實。

## 這場拆成五份，按用途分

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [要拿去問使用者的問題](questions-for-user.md) | 〈要拿去問使用者的問題〉八題，第一題是四位都問到的核心 | **本場最主要的產出；要往下推進就先回答這裡。** |
| [轉交提案](handoff.md) | 〈轉交提案（未拍板，不自行改規格／roadmap）〉六條 | 問題有答案之後，要決定先做哪一塊時 |
| [現在可能痛在哪（全部是推論）](pain-points.md) | 〈`workflows` 現在可能會痛在哪〉：open-only 靠記憶、安裝升級沒有上游基準、inbox 生命週期、派發與遵守流程、tick 與 schedule | 想知道這些問題是怎麼推出來的，或要確認哪些只是假說 |
| [哪些交給 `.aos`、哪些留在 markdown](machine-vs-markdown/README.md) | 再拆成三份：[該變成 `.aos` 的](machine-vs-markdown/to-aos.md)（共同長出的動作、兩個磁碟版面、候選動作順序、安裝與升級）、[該永遠留在 markdown 的](machine-vs-markdown/stay-in-markdown.md)、[三軸分別長成什麼](machine-vs-markdown/three-axes.md) | 要設計命令、磁碟版面，或決定什麼不該被編成 JSON 時 |
| [還在生長的想法與明顯的坑](open-issues.md) | 〈還在生長的想法〉五條、〈明顯的坑〉 | 想知道哪些還沒收攏、哪些做法已被四位否掉 |

## 續場資訊

本輪沿用前幾場的四個 codex session；它們仍保留完整前情。session id **只在 office Windows
那台機器有效**；`codex exec resume <id>` **不吃 `-s` 與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

> 原本是單檔 `workflows-on-aos.md`，一輪跑完膨脹到 22 KB，照 [DEV-GUIDE](../../../../STRUCTURE.md) 的「膨脹即拆」按用途拆成本資料夾。
