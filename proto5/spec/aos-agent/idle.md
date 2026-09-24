← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 8. idle：收輸入

0. （09-24 第 4 隊補）`intake` 是 null 時，先看要不要自動壓縮記憶（[agent/compact.md §4](../agent/compact.md)）：在同一把 tick 鎖裡做，縮了（或收了 compact 申請）這格就退 0。
1. `intake` 是 null：列出 `input` 指到、現在存在的檔（[agent.md §4.1](../agent/state.md)）。一個都沒有＝退 102（09-24 停車；以前是 101）。
   有 → 取新的消費 id，**寫 state**：`intake = {"id", "base_len": 現在記憶長度, "files": [{"src", "dst": 封存名}…]}`（封存名 `<src 所在資料夾>/done/<src 檔名>.<id>.done`（09-24 試玩 r1 補））。這一步還沒讀內容。
2. 逐對搬（[agent.md §4.4](../agent/state.md)：`dst` 在＝搬過了、不碰 `src`；`dst` 不在 `src` 在＝rename；都不在＝那份被人拿走了，讀的時候跳過）。
3. 從每個 `dst` 讀訊息、照 agent.md §3.2 驗。壞檔＝退 1，**已寫的 `intake` 與已搬的檔都留著**。人要處理：就地改好那個 `dst`；
   或照 [agent.md §4.4](../agent/state.md) 放棄那一對（先 stop、在 state 裡拿掉那一對、才動 `dst`）——只刪 `dst` 不改 state，下次會去搬原路徑上的新檔。全部略過＝沒輸入：寫 `intake: null`、退 0（09-24 停車：寫了 state，下一格重看輸入與壓縮；這裡停車可能吞掉剛投的輸入的叫醒）。
4. 記憶寫成「前 `base_len` 則＋讀到的訊息」（長度檢查同 §7；其他＝`HistoryChanged`）。
5. **寫 state**：`state: think`、`intake: null`。退 0。（09-24 第 4 隊補）寫 state 之前記一筆事件 `intake`（[agent/events.md](../agent/events.md)）。

崩在 1 之後任何地方：下次看到 `intake` 從第 2 步重做。讀的永遠是封存名，內容不會變；同一份訊息不會接兩次；
原路徑上新投的同名檔不會被這次恢復搬走或吞掉，留給下一次收。
