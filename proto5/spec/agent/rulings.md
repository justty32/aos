← [agent](README.md)｜[spec 總導航](../README.md)

# 調度者裁決（第 2～3 輪，實作層級）

1. 在途工作的身分只記在 `state.batch`（§4.3），`waits` 只剩外人的門；aos-agent 不再往 `waits` 加自己的條目。
2. `info.kernel`、`info.llm.config` 拿掉：K 由 `AOS_K`（09-24 fix-r4 改名 `AOS_KERNEL_HOME`）給、送件時記進 `batch.kernel`；模型表在 llm cpu 那邊。
3. 新增 `info.tick`（`pool`、`interval_ms`）給 `aos-agent start` 登記用。
4. 四個工作資料夾併成一個 `work/`，檔名 `<工作名>.inst.json`／`.in`／`.out`，清檔一條規則。
5. `waits` 的選項只剩 `consume`；`exists`、`all` 可寫但就是預設（陣列＝全到才算）。
6. 程式自己寫的 `state` 各格（除了 `input`）必須是字面值，不吃指示詞。
7. 記憶的 message 驗證寫死在 §3.2，`aos-llm call` 與 aos-agent 共用同一套。
8. （第 3 輪）**每次消費一個身分**：輸入與 consume 的檔先 rename 到唯一的封存名 `<原名>.<消費 id>.done`、再讀；state 記的是「原路徑→封存名」對，恢復只認封存名，不再碰原路徑上可能新投遞的檔（§4.4）。
