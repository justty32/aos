# daemon 訊息模組與 aos-mq

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜格式：[P-125](../protocol/daemon/mq.md)｜舊設計：[暫緩區 B-614](../deferred/daemon/messaging.md)

程式：`lib/aos_daemon_mq.py`、`lib/aos_mq.py`；測試：`tests/test_mq_doors.py`、`test_mq_send.py`。

## B-645：訊息模組與 aos-mq

做什麼：daemon 開幾扇「門」（各一個 unix socket，`modules.mq` 是「門名 → 路徑」），每一項用 `mq` 陣列自己挑訂哪幾扇。從某扇門寄進來的信，原樣放進訂了那扇門的每一項的信箱，並叫醒它們。任務用 `aos-mq send|take|peek <門>` 收發。

原則：

- **門就是收件地址**：沒有頻道、沒有收件人欄位，訂了誰就給誰。信是寄的 JSON 原樣，daemon 不加任何欄位；要知道誰寄的、怎麼回，寫在信裡自己約定。跨 daemon 就是寄到對方的門。
- 叫醒會合併（等於不帶選項的 `wake`）：開跑前連來幾封只跑一次，正在跑時來信跑完補一次；所以不需要「急件」。
- 信箱每項一個、放記憶體、先進先出，重開就丟，不保證送達、不設上限、不去重。
- **socket 一律 666，誰能連靠所在資料夾**（見 [README](README.md)）；daemon 不驗身分。`aos-mq` 只取自己（`AOS_DAEMON_INST`）的信是 `aos-mq` 這側的禮貌，不是 daemon 的保證；要擋人，就把門放進權限對的資料夾（例：只准 ops 群組的門放在 `root:ops 0750` 的資料夾）。
- 環境變數：每扇門一個 `AOS_DAEMON_MQ_<門名>`（不管有沒有訂）；`AOS_DAEMON_INST` 控制或訊息任一掛了就放。
- 設定錯：訂了不存在的門、兩扇門同路徑或跟控制 socket 同路徑。
