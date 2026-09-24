# daemon 按池對帳：補、收、重拉、節流

← [spec 導航](README.md)｜存檔：[daemon-home](daemon-home.md)｜收到的單：[protocol](protocol.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/daemon.md](../../proto5/spec/daemon.md) §4（一圈）、§5 的停機階梯寫法、§9 第 1、2 條（退 0 不重拉、固定間隔無退避）**。
> 孩子怎麼拉（§2 的 fork、`go` 握手、process group、每次重讀 target）不變，只有 pipe 少一條（§5）。

一句話：**daemon 手上是一份「每池要哪幾號」的宣告；每一圈把實際的孩子往宣告靠——少了補、多了收、死了等一下再拉。**
它不問 kernel、也不需要 kernel 每格來確認。

## 1. 一顆孩子的狀態

```text
         宣告加了這號                 輪到它（節流）、拉成功
(不存在) ─────────────▶ pending ─────────────────────────▶ running
                           ▲                                │  │
                 kill／重拉等到了、拉成功 ◀── dead ◀── 死了（還是成員）│
                           │                                  │
                         failed ◀── 拉不起來（SpawnFailed）        │
                                                              ▼
                      不再是成員、或被 kill ─────────────▶ killing ──死透──▶ 還是成員：pending（kill＝重來）
                                                                         不是成員：刪 kids 檔，消失
```

- `pending`、`dead`、`failed` 的號**不是成員了**（宣告縮小）：直接拿掉，不用走階梯。
- `running` 的號不是成員了：進 `killing` 走階梯。
- **任何退出碼都一樣**：成員死了就是 `dead`、等一下再拉。proto5 的「退 0＝孩子自願停、不重拉」拿掉——宣告式下，要它停的唯一方法是把它移出宣告（或 daemon 停機）。

## 2. 一圈

```text
1. 處理 requests/ 的 ack-、stop-（同 proto5）
2. 處理其他單：scale、kill、ls（protocol）。scale 只改宣告、標這池「要對帳」
3. 收屍：waitpid(-1, WNOHANG) 一直收到沒有——只碰死掉的那幾個，不逐顆問
   killing 的：還是成員 → pending（不加 streak）；不是 → 刪 kids 檔
   running 的：還是成員 → dead，streak 照 §3 算，寫 kids 檔；daemon 在 stopping → 拿掉
4. 對帳（只對「要對帳」的池）：新加的號 → pending；拿掉的號 → 照 §1 收
5. 拉：從「pending＋到期的 dead／failed」裡拿，最多拿到節流額度（§4），拉（proto5 §2 那套）
6. 推進停機階梯（§6），只看到期的那批
7. 有變的池重寫 summary.json
8. 睡到 poll_ms 或下一個到期時間，取較短的
```

每一圈的成本只跟「這圈有事的」成比例：新單、死掉的、輪到拉的、階梯到期的。上萬個安靜的孩子不佔一圈的時間。

## 3. 重拉要等多久（節流一：每顆）

```text
等待 = min(restart_delay_ms × 2^(streak−1), restart_max_ms)
```

- 死的時候，這一代活超過 `stable_ms` → `streak` 先歸 0 再加 1（當第一次死）；否則 `streak` 加 1。
- 預設：1 秒、2 秒、4 秒…最多 60 秒。一直崩的那顆會降到每分鐘試一次，而不是 proto5 的每秒一次。
- `SpawnFailed`（target 讀不到、inst 壞掉）一樣算：進 `failed`、`streak` 加 1、照同一條算式等。宣告換了 `target` 時，這池所有 `failed` 的等待清掉、馬上可以再試。
- `kill` 造成的死不加 `streak`、不用等（人叫的）。

## 4. 同時拉幾顆（節流二：整個 daemon）

- 令牌桶：每秒補 `spawn_per_sec` 個、最多存 `spawn_per_sec` 個；拉一顆用一個（成功失敗都算）。
- 池之間輪流拿，一池一次拿一顆，免得一個大池長大時把別的池的重拉餓死。
- 上萬顆的池從 0 長到 10000：預設 50 顆／秒，約 200 秒拉滿。kernel 那邊不用等，派到還沒起來的號單會在家裡等。
- 全池一起死（例如 PATH 壞了）：第一輪最快也是 50 顆／秒，之後各自退避，不會變成每秒 fork 一萬次。

## 5. 管子與開檔數

proto5 每個孩子兩條 pipe（四個端點在 daemon 手上，關掉孩子那兩端後還留兩個）。上萬個孩子就是兩萬個 fd。這一版：

- **只留 fd 0 那條**（daemon 寫、孩子讀 `go`／`stop`、看 EOF）；孩子的 fd 1 接 `/dev/null`。
  proto5 那條 fd 1 本來就「讀走就丟」，孩子不往上寫（daemon.md §2）。**取代 daemon.md §2「fd 0、fd 1 一律接成控制 pipe」**。
- 啟動時把開檔數軟上限調到硬上限；實際能管的孩子數＝min(`max_children`, 開檔數 − 64)。scale 超過就回 `TooMany`（[protocol](protocol.md)）。
- 行程數上限（`ulimit -u`）、記憶體不在 daemon 的檢查範圍：fork 失敗就是 `SpawnFailed`，照 §3 退避。

> 實作先驗：[cpu.md §6.1](../../proto5/spec/cpu.md) 第 3 步在「fd 0 是 pipe」時會把 fd 0／fd 1 都搬到高位；fd 1 是 `/dev/null` 時要確認 cpu 不會因此出錯（它從不寫那條）。

## 6. 停機階梯：一批一批做

階梯三段（pipe 說 `stop` → TERM → KILL 整組）與時間同 proto5 §5。差在**做法**：

- 同一圈要收的孩子是一批：這一圈就對整批每個孩子的 fd 0 寫 `stop`（非阻塞；EAGAIN 下一圈再寫），整批共用一個到期時間。
- 到期時只看那一批裡還活著的，一起送 TERM，下一個到期再一起 KILL。
- 到期時間放在一個按時間排的佇列裡，每圈只拿到期的批，不逐顆檢查。

這樣 `halt` 一萬個孩子是「一圈寫一萬行 stop、等 5 秒、一圈送還活著的 TERM、等 5 秒、再一圈 KILL」，而不是一萬個各自的計時器。

## 7. daemon 停機（`halt`）

同 proto5 §5：`stopping` 設起來、所有 `running` 的進一批階梯、`pending`／`dead`／`failed` 的直接拿掉、`scale` 回 `Stopping`、`kill` 照常。
全部孩子不在了：`pid` 寫 0、放鎖、退 0。**`pool.json` 留著**——下次開 daemon 會照宣告把孩子拉回來（[handoff §2](handoff.md)）。
不想要它們回來，就先讓 owner 把池縮到 0（kernel 的 `halt` 就會這樣做）。
