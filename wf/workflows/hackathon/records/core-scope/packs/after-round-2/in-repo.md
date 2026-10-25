# 第 2 輪之後的資料包 — repo 裡已經有答案的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1 後](../after-round-1/in-repo.md)

## 3. repo 裡已經有答案的

- `core/inst/src/handoff.cpp` `aggregate_instructions()`：「`rename(paths.temp, paths.base)` 成功 → `result.published = true` → `remove_accepted_deliveries()`」是現行精確順序；沒有 acknowledgment，只有發布後刪來源 delivery。
- `core/inst/docs/handoff.md`〈彙整規則〉與 `docs/roadmap.md`〈T3 — 彙整與發布：接出下一回合〉：「發布成功之後才刪投遞」；`core/inst/tests/test_handoff.cpp`〈handoff aggregates deliveries in filename order and flattens batches〉可改造成測例。
- `core/inst/docs/capi.md`〈讀取、寫入與執行〉：C ABI 的 `aos_instruction_read_buffer()` 只接受單筆 object、不接受 batch array；檔頭明寫 C ABI 沒有 batch／handoff API。
- `core/inst/src/format.cpp` `read_all()`：object／array 共用、失敗時整批不交付、回報 one-based `error_record` 的 canonical batch parser；`core/inst/tests/test_format_read.cpp`〈read_all accepts a single instruction object〉〈read_all accepts a formatted array〉〈read_all is atomic and reports a one-based record number〉可當 conformance cases。
- `docs/inst-directives.md`〈六、擺在哪一層？〉與 `core/inst/docs/architecture.md`〈架構〉：`format` 是唯一懂 instruction schema 的分層，`resolve`、`handoff`、`exec` 不得重新解讀 schema。
- `docs/aos-folder.md`〈十二、留給實作決定的〉〈仍然開著的〉：殘存 `.bad`／`.runi` 清理的容量上限方向與「不能自動清掉 crash 現場」的衝突，可作 transaction 目錄與孤兒 temp 保留政策的邊界資料。
