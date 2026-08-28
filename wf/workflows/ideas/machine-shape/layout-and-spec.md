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

