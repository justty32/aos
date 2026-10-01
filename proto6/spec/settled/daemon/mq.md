# daemon 訊息模組與 `aos-mq`：每項一個信箱

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜[記住狀態 B-643](state.md)｜[收屍／cgroup B-644](cgroup.md)｜格式：[P-125](../protocol/daemon/mq.md)｜舊設計：[暫緩區 B-614](../deferred/daemon/messaging.md)

本篇只有 B-645，寫訊息模組**做什麼**。socket 上的請求與回應、`aos-mq` 的用法與錯誤代碼，寫在格式篇 [P-125](../protocol/daemon/mq.md)。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)、[plan m3m 模組四](../../../plan/m3m-daemon-modules.md#模組四訊息modulesmq)；現行程式 [訊息與 aos-mq](../../../src/py/README.md#訊息與-aos-mqm3m-模組四)（`lib/aos_daemon_mq.py`、`lib/aos_mq.py`，有出入以程式為準）。

## B-645：訊息模組與 `aos-mq`〔使用者 2026-10-01 第十二批〕

**daemon 的每一項一個信箱；任務用 `aos-mq send` 寄信給別項、用 `aos-mq take` 取自己的信；急件順便叫醒收件那一項。** 它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了 `modules.mq` 才有。

**收件人是 daemon 的一項**（`insts` 的鍵，逐字比對），不是 node、不是資料夾；inst 是檔也收得到信。

### socket

- daemon 另開一個 unix socket，**不走控制 socket**（使用者 m3n 裁定 5）；兩個模組各開各的、互不依賴。
- 協議照控制模組：一連線一請求、一行 JSON 來、一行 JSON 回（[B-641](control.md)）。能連 socket 就能寄給任何一項、取任何一項的信，不另外檢查權限。
- 壞請求、對面先關、逾時只影響那一條連線。
- 收到 SIGINT／SIGTERM 退出前刪 socket 檔（同控制模組）。

### 信箱

- **每一項一個信箱，放 daemon 記憶體、先進先出。** daemon 重開就丟，不保證送達。
- 一封信是 `{"from": <寄件 inst 或 null>, "msg": <任何 JSON 值>}`。daemon 不看 `msg` 是什麼；`from` 原樣存、不核對（使用者同意 M1：能連 socket 的人本來就能冒充）。
- **取信一次全部取走**、信箱清空。誰都可以取任何一項的信（使用者同意 M3），先取先得。
- 寄給不在 `insts` 的項：回 `unknown_inst`，信不收。
- 不設上限（每箱幾封、單封多大）、不去重、不確認送達、不重送。

### 急件

寄的時候標 `urgent`：信放進信箱後，**照控制模組 `wake`（不帶選項）的規則叫醒收件那一項**——正在跑就跑完補一次（連寄幾封急件都只補一次）、暫停中跑一次（跑完照樣暫停）、已停不跑（信照樣收下、回成功）。不用掛控制模組也做得到；以後 `wake` 的規則改了，急件跟著改。

### 給任務的環境變數

掛了之後每次開 `aos-exec` 多放：

- `AOS_DAEMON_MQ_SOCKET`：訊息 socket 的絕對路徑。
- `AOS_DAEMON_INST`：這一項的 inst 字面值。**掛了控制或訊息任何一個就放**（使用者同意 M2），兩個都掛也是同一個值。

### `aos-mq`

```text
aos-mq send [--urgent] <收件 inst> <JSON|->
aos-mq take [<inst>]
```

- socket 只從 `AOS_DAEMON_MQ_SOCKET` 拿。
- `send`：`from` 自動填 `AOS_DAEMON_INST`（沒有就 `null`）；`<JSON>` 給 `-` 就從 stdin 讀。
- `take`：沒給 `<inst>` 用 `AOS_DAEMON_INST`；每封一行印到 stdout，沒信什麼都不印。
- 成功回 0；其他一律回 1（[C-08](../conventions.md)），stderr 一行代碼與說明。
- 名字照使用者同意 M4：程式叫 `aos-mq`、子命令 `send`／`take`、模組鍵 `mq`。tick 側舊的 `aos-mq get`／`post`（[B-623、B-624](../tick/mq.md)）是「讀寫 `.aos/mq/` 檔」的系統級任務，意思不一樣，照舊待實作；任務裡要收發信直接叫 `aos-mq send`／`take`，tick 核心不用改。

### 跟其他模組

- **控制模組**（[B-641](control.md)）：各開各的 socket；急件直接動那一項的狀態，不經控制 socket。
- **重讀設定**（[B-642](reload.md)）：還在的項信箱照留；拿掉的項連信箱一起丟，之後寄給它回 `unknown_inst`；拿掉又加回來＝新的一項，信箱從空的開始。換 socket 路徑算 `modules` 改了：不套用、警告要重開。
- **記住狀態**（[B-643](state.md)）：信不記。
- **收屍／cgroup**（[B-644](cgroup.md)）：沒關係。

### 先不做

信箱上限、寄件權限、送達確認／去重／重送、跨 daemon 送信、訊息格式檢查、tick 側的 `.aos/mq/` 檔案流程。舊設計的 node 收件人、`node.send`／`node.take`、通道憑證、寫權授權、急件越過上層節流都在[暫緩區 B-614](../deferred/daemon/messaging.md)。

依據：使用者 2026-10-01 第十二批：訊息要做、排在 cgroup 之後，M1～M4 照建議。

**驗收：**兩項 a、b；a 的任務 `aos-mq send b '{"hi":1}'` 回 0，b 的任務 `aos-mq take` 印出 `{"from":"a","msg":{"hi":1}}`，再取一次什麼都不印；先寄的先取到；`--urgent` 寄給週期 1 小時的 b：b 一秒內跑一次，普通信不叫醒；b 正在跑時連寄三封急件：只補跑一次、三封一次取到；急件寄給已停的項不跑、信照收；暫停的項跑一次、照樣暫停；寄給不存在的項：回 1、`unknown_inst:`；沒有 `AOS_DAEMON_MQ_SOCKET`：回 1、`no_daemon:`；壞請求只影響那一條連線；daemon 重開後信箱是空的；重讀設定時還在的項信照留、拿掉的項寄信回 `unknown_inst`、加回來信箱是空的；沒掛模組：原有測試全過。測試見 `proto6/src/py/tests/test_mq.py`。
