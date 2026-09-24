← [kernel](README.md)｜[spec 總導航](../README.md)

# 1.1 `info.json`：池表（第 2 版）

（2026-09-24 proto5-2 池式納入，取代第 1 版的 `cpus` 表。）家的長相見 [§1](home.md)；池怎麼增減見 [§3.1](pools.md)。

一句話：**kernel 不再一顆一顆列 cpu，只列池**——池叫什麼、交給哪個 daemon、在 daemon 那邊叫什麼、要幾顆、帶什麼環境。
cpu 是哪一種（一般、問模型的…）由池的 `envs` 決定，進這個池的每一顆都一樣。

## 範例

```json
{"_metainfo": {"_type": "kernel", "_version": 2},
 "daemon": "/abs/D",
 "pools": {
   "kernel":  {"count": 1, "dpool": "k1-kernel"},
   "default": {"count": 8, "dpool": "k1-default"},
   "llm":     {"count": 2, "dpool": "k1-llm",
               "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}},
   "gpu":     {"count": 3, "daemon": "/abs/D2", "skip": [1]}},
 "cpu": {"poll_ms": 200, "timeout_ms": 0},
 "tick_ms": 1000, "interval_ms": 1000, "timeout_ms": 0,
 "done_exit": 100, "bad_after": 10, "sweep": 32}
```

## 欄位

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo._version` | 整數 | 必填 | 只認 2。讀到 1（舊的 `cpus` 表）＝`InfoVersion`、退 1，請人照本檔改寫 |
| `daemon` | 絕對路徑 | 見下 | 預設的 daemon 家。每個池都自己寫了 `daemon` 就可以省 |
| `pools` | 物件 | 必填 | key 是池名 P（合法檔名、不含 `/`）；值見下幾列 |
| `pools.P.count` | 非負整數 | 必填 | **要幾顆**。0＝池在但沒 cpu，派到這池的行程就一直排隊（不算錯） |
| `pools.P.daemon` | 絕對路徑 | 頂層 `daemon` | 這池交給哪個 daemon |
| `pools.P.dpool` | 字串 | P | daemon 那邊的池名。同一個 daemon 家底下兩個池的 `dpool` 撞名＝`FieldTypeMismatch` |
| `pools.P.envs` | inst 的 `envs` 格 | `{}` | 這池每顆 cpu 帶的環境；原樣寫進 `K/pools/P/envs.json`，不解 |
| `pools.P.skip` | 非負整數陣列 | `[]` | 退休的 cpu 編號（見下「編號」） |
| `cpu` | 物件 | 見右 | 工作池每顆 cpu 家的 `info.json` 設定：`poll_ms`（預設 **200**）、`timeout_ms`（預設 0）。kernel 建家時抄進去 |
| `tick_ms` | 非負整數 | 1000 | 一格睡多久（§3 第 3 步） |
| `interval_ms` | 非負整數 | 1000 | 行程 `interval_ms` 的預設 |
| `timeout_ms` | 非負整數 | 0 | 行程 `timeout_ms` 的預設；tick 自己不限時 |
| `done_exit` | 0～255 | 100 | 反覆行程回這個碼＝完成；0＝關掉 |
| `bad_after` | 非負整數 | 10 | 連續失敗幾次退件；0＝關掉 |
| `sweep` | 正整數 | 32 | 每格巡檢幾顆忙的 cpu（§3 第 6 步） |

- **kernel 池**：池名固定叫 `kernel`；沒寫就當 `{"count": 1}`。`count` 只能是 1、`skip` 只能是空的（別的＝`FieldTypeMismatch`），所以它永遠是 0 號。
  一般行程不准進這池（`add` 的 `pool: "kernel"`＝`-32602`）。
- `cpu.poll_ms` 預設從 cpu 範式的 20 提高到 200：上萬顆每 20 ms 掃一次資料夾太吵。代價是派工延遲多最多 0.2 秒。kernel 池那顆照舊 20。
- 整份解指示詞，中心是 K，不提供 `$opt`（`envs` 那格例外：它是要寫進池的 `envs.json` 的，原樣留著不解）。
  **頂層必須是字面物件**（頂層整份 `$ref`＝`FieldTypeMismatch`）。boot 把整份驗完才動任何東西（§6）。

## 編號：池裡有哪幾顆

池 P 的成員＝**不在 `skip` 裡的最小 `count` 個非負整數**，名字就是十進位字串。例：`count 3, skip [1]` → `0`、`2`、`3`。
一顆 cpu 的全名是 `P/<i>`，家在 `K/pools/P/cpus/<i>/`。

為什麼用編號、不讓 daemon 自己取名：
- kernel 不用問 daemon 就知道池裡有哪幾顆，派工時直接往那顆的家放單；daemon 只要照同一條公式拉。
- 縮小時一律先收最大的號；再長回來會用回同一個家——同一個家換下一任主人，剩下的單由 [cpu 範式 §6.2](../cpu/lifecycle.md) 的開機對帳處理，本來就支援。
- **任何一組編號都寫得成 `count`＋`skip`**：把集合最大號以下的空洞全放進 `skip` 就是了。所以 kernel 跟 daemon 之間只傳這兩格（[daemon §3](../daemon/methods.md)）。

**`skip` 用在哪**：某一顆的家壞了、想讓它永久退休。`aos-kernel cpu rm P/1` 就是把 1 放進 `skip`、`count` 減 1——
其他顆不動、也不會補一顆新號。**退休號只增不減**：寫進 `skip` 的號永久保留，之後 `cpu add` 長大也不會用回那號；
要讓它回來只能手改 info 把它拿掉。（09-24 裁定，實作 D-4／D-38：永久退休優先於 `skip` 長度。）

## 改 info 什麼時候生效

tick 每格重讀 info。池的 `count`／`skip`／`envs` 變了，**下一格**就照 [§3.1](pools.md) 處理，不用 boot。例外：
- kernel 池的任何欄位只在 boot 生效（帳本裡的 kernel 池才算數）。
- 池改 `daemon` 或 `dpool`（搬池）：tick 照帳本裡的舊位置先把舊池縮到 0，**等舊 daemon 把那池整個拿掉**（它的 `summary.json` 確定不在）才換新位置、開始宣告；
  在那之前 ls 印 `搬池中`。池從 info 刪掉又加回也一樣：帳本那格要等舊池消失才忘掉，加回來就接著用那格。
  這樣同一批 cpu 的家不會同時被兩個 daemon 的孩子當家。例外：那個位置**從沒被 daemon 確認過**（例如第一次宣告就撞 `NameTaken`），直接換新位置，不等舊池（實作 D-49）。
- `cpu` 那格只影響之後才建的家（建家是「缺的補齊、不覆蓋」，§1）。
- 改池的 `envs`：重寫池的 `envs.json`，之後（重）拉的 cpu 生效；活著的不換（§1 池模板）。

## 讀驗邊界

| 項目 | 規則 | 錯了 |
|---|---|---|
| 池名、`dpool` | 1～64 bytes，只用 `A-Z a-z 0-9 _ . -`，不能是 `.`／`..`；不能含 `{`、`}`、`#`、`/` | `FieldTypeMismatch` |
| cpu 全名 | `P/<i>`，`i` 是不帶前導 0 的十進位（`P/01` 不合法） | CLI 用法錯 2 |
| `count` | 非負整數，bool 不算；上限 1000000 | `FieldTypeMismatch` |
| `skip` | 非負整數、不重複；CLI 寫入時排好序、去重，**不丟任何一號**（大於最大成員號的也留著） | `FieldTypeMismatch` |
| `daemon` | 每個池都要解得出一個 daemon 家；init 時可以還沒有，**boot 才檢查**（`NoDaemon`） | boot 退 1 |
| `cpu.poll_ms` | 正整數；`cpu.timeout_ms` 非負整數 | `FieldTypeMismatch` |

`aos-kernel cpu add／rm` 就是改這份檔（[§6 cpu](cli-cpu.md)）；人手改也行。
