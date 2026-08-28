# 資料夾結構、所需程式、規範
← [machine-shape](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

**驗證過**：handoff 的 `aggregate`／`claim`／`release` **一個都沒進 C ABI**，也沒有 `deliver`。

## 10. 命名標準延伸不到 loop 接下來要加的東西

已定案 `<名字>.<副檔名>.<狀況>`，狀況只有 `.temp`／`.runi`（實作已偷偷多了 `.bad`）。但
loop 要加 **events**（append-only 事件流）與 **status**（當下投影）——**那些不是
`inst.json` 的「狀況」，是不同的物件**，塞不進三段式命名。

`.aos/` 現在只有一個軸（inst 的各種狀況），需要的是兩個軸：**哪顆 CPU × 哪一類物件**
（佇列／現場／歷史／投影／交換區）。這是「資料夾結構」最近會撞到的一件事，**現在改比
之後改便宜得多**。

## 11. 最該有的那支程式正好沒有：**沒有 `deliver`**

handoff 提供的 `aggregate`／`claim`／`release` **全是消費端**，而且**都沒進 C ABI**。
**投遞**——唯一由**外部生產者**執行的那一步——既沒有函式也沒有子命令。

於是每個生產者都得自己手刻：組 `<pid>.json.temp`、寫、rename、pid 撞名自理、`.temp`
中途失敗自清。**這是整套協定裡最容易寫錯的一步，也是唯一沒有實作提供的一步**，而生產者
將來主要是 LLM 與外部工具。

`aos deliver <folder>`（吃 stdin 或檔案）＋ 一個 C ABI 的 `deliver`，是**成本最低、擋掉
最多真實故障**的補丁。

## 12. 規範已經有三份真相，而且在漂

`docs/aos-folder.md`（規格）、`core/inst/docs/*.md`（實作文件）、手寫的 C++ parser（實際
行為）。`.bad` 證明漂移已發生：**實作有規格不知道的狀況字**。第四份真相是 **LLM 對格式的
理解**，取決於它讀到哪份文件。

對一個以「讓 LLM 生成指令」為核心用例的 ISA，需要**一份機器可讀的 schema**（JSON
Schema），讓 parser、文件與餵給 LLM 的 prompt 都從它派生。現在是三處手工同步——
conventions 那條「新增／改欄位要全域 grep 受影響處並同一 commit 更新」的存在，本身就在說
這裡有結構性重複。

## 16. 版面沒有版本

`.aos/` 沒有 `version` 之類的東西，而 loop 即將加 events 與 status，**版面一定會變**。

這跟 [instruction](instruction.md) 第 2 條的「格式沒有版本」是**兩件不同的事**：一個是
**指令格式的版本**（一份 `inst.json` 的 schema），一個是**版面的版本**（`.aos/` 的結構）。
兩個都缺，兩個都是一個檔案就能解決。沒有版面版本，新舊 aos 遇到對方的資料夾時沒有任何
偵測手段，只會以 `UnknownKey` 或「找不到檔案」這種下游症狀爆出來。

## 17. 沒有控制介面：不能問狀態、不能暫停

loop 就是一個前景行程，`exec --loop` 起、Ctrl-C 停。沒有：

- **`aos status <folder>`**——這個世界在跑嗎？跑到第幾回合？（回合編號也還不存在）
- **pid 檔或 socket**——外面沒有東西找得到它。
- **暫停**——世界的生命週期只有兩個狀態：跑，或死。沒有「停在回合邊界」。

而「使用者可以在回合之間介入」是這個模型的核心賣點。**目前介入的方式是賭在兩個回合之間
手快**，沒有機制讓人說「下一回合結束後停下來，我要看一下」。

這與第 11 條的 `deliver` 是同一類：**協定和模型都假設有這些操作，但沒有一支程式提供。**


---

# 第十輪（換 Fable 重打）：ownership、名冊封閉、normative 的家

**全部未裁**——使用者：之後慢慢想，更可能邊實作邊想。

## 28. 版面規格的內容是 ownership table，不是檔名列表

datasheet 的 memory map 每格標 R/W/RO/W1C。`.aos/` 至少三類 writer：loop
（claim/release）、外部生產者（tempd 投遞）、未來的 events/status writer——再加 LLM CPU
寫回結果。**每條路徑該標唯一 writer 與方向；有兩個 writer 的路徑，就是未來損壞的準確
位置。** 第 10 條的「第二個軸」解決分類，ownership 解決正確性——`docs/aos-folder.md`
目前只記「有什麼」，沒記「誰能動」。

## 29. 程式名冊有封閉判準，不必累積

從協定推導：**外部方執行的每個協定步驟→一支程式**（`deliver`，第 11 條）；**機器留下
的每種靜態狀態→inspector＋repairer**（`status`、`recover`＝這台機器的 fsck，T5 規格
已有）；**每份規範→validator**（`aos check <folder>`：版面對不對、schema 過不過——
這支連規格都沒有，而它是三份真相收斂的機械手段）。名冊＝ `exec`／`loop`／`deliver`／
`status`／`recover`／`check`，**到此封閉**。T5 的 `agent step`／`emit-context` 按此
判準是 OS 層→按 [loop 第 25 條](loop.md)該是 inst，不是子命令。

## 30. 機器的憲法散在拷問記錄裡，沒有蓋章的地方

「一回合內沒有資料流」——最重要的 ISA 約束——住在 ideas 檔的第 18 節；
[verdicts](../verdicts.md) 是**判例索引**，不是法典。三份真相在漂（第 12 條）的根因：
**沒有任何一份文件被指定為 normative**，每份都只是描述，描述之間當然漂。「地位」的
操作型定義很無聊：一份編號條款、MUST/SHOULD、其他一切（parser／docs／prompt）從它
派生的 SPEC，加上「裁決如何進入它」的流程。沒有它，第十九輪還會發現「最重要的約束
沒寫在任何地方」。

> **裁決（2026-08-28）**：**已立法**——[`docs/SPEC.md`](../../../../docs/SPEC.md) 建立，
> 編號條款、MUST/SHOULD、每條附來源、開頭寫「裁決如何進入本檔」。§18 現在是 SPEC §A-3。
