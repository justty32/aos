# kernel 家（第 1 版）

← [README](../README.md)｜程式：[aos-kernel](aos-kernel.md)｜[inst](inst-posix.md)

Kernel 排程的每個行程都是普通 posix inst；agent、llm cpu、tool cpu 沒有特別身分。沒有 module。

## 目錄

| 路徑 | 意義 |
|---|---|
| `info.json` | kernel 身分與排程設定 |
| `inst.json` | kernel 自己的 tick；cwd 是 K，argv 是 Python 與 `cli/aos-kernel tick` 的絕對路徑 |
| `state.json` | 原子替換的排程快照，見下 |
| `procs/<NAME>.json` | 等候執行的完整 posix inst |
| `procs/done/<NAME>.json` | 回 done_exit 的行程 |
| `procs/bad/<NAME>.json` | 無法讀驗、連敗或 aos 執行錯誤的行程 |
| `cpus/<N>.json` | 第 N 顆 CPU 現在的 inst；N 從 0 起，閒置為無副作用的 Python 指令 |
| `cpus/<N>.json.lock` | 穩定 slot 鎖；init 建立，永不替換或刪除。空檔可跑；首 byte `Y` 請 run 做完本格後等候；鎖供執行與換檔共用 |
| `.kernel.lock` | tick／add 的 flock，保護 state 與檔案指派；重疊 tick 直接退 0 |
| `syscalls/<單名>.json` | 唯一 syscall：`{"op":"rm","pid":"NAME"}` |
| `syscalls/done/<單名>.json` | 回音 `{"ok":true,"msg":"removed NAME"}`；失敗另有 `code` |
| `kernel.log` | 每格 append 排程／退件記錄；tick stderr 也 append 於此 |

CPU 上的行程檔從 procs 搬到 cpus，不同 CPU 不得同時擁有同一 NAME；queue 內也不能重複。NAME 是非空檔名，不能是 `.`／`..` 或含 `/`／NUL。自動名字為所有 active／done／bad 數字名最大值加 1。具名 add 不覆蓋任何已存在名字；rm 能移除 active／done／bad。

## info.json

```json
{
  "_metainfo": {"_type": "kernel", "_version": 1},
  "ncpu": 3,
  "interval_ms": 1000,
  "timeout_ms": 0,
  "quantum": 5,
  "done_exit": 100,
  "wait_exit": 101,
  "bad_after": 10
}
```

整份 info、每個設定、metainfo 及其中兩欄都解 [指示詞](directives.md)，中心路徑是 K。不提供 `$opt`；解完驗型別。ncpu 必填正整數，其他欄缺省如上；bool 不是整數。interval_ms／timeout_ms／bad_after 可為 0，quantum 至少 1。done_exit 是 0～255（0 關閉完成判定），wait_exit 是 1～255，兩者不得相同。bad_after=0 關閉一般子程式連敗退件。timeout_ms 只限制每顆工作 CPU 的一次執行，kernel 自己的 tick 不設 timeout，避免等 daemon 回音時被截斷。

init 只吃 ncpu，其餘設定修改 info；ncpu 不應在有指派時縮小，超出範圍的 state 會被拒。info 不是瞬間變更既有 runner 旗標的控制台：既有 CPU runner 的 interval／timeout 在下一次重建才採新值，boot 的 kernel 間隔在重新 boot 後生效。

## state.json

```json
{
  "cpus": {
    "0": {"pid":"one", "since":1790000000.0, "runs_at":0, "seen_runs":2,
          "waiting":false, "wait_runs":0, "bad_runs":2, "bad_exit":7, "aos_ticks":0},
    "1": null
  },
  "queue": ["two"],
  "waiting": {"two":{"waiting":true,"wait_runs":1,"bad_runs":0,"aos_ticks":0}}
}
```

cpus 的 key 是 CPU 編號字串，null 表示 idle。pid 是 kernel 行程 NAME，不是 Linux pid；since 是上 CPU 的 Unix 秒數。runs_at／seen_runs 是目前 daemon runner 的完成次數基線與已觀察次數，每次重建 runner 歸零；since 只供記錄。

waiting／wait_runs 記錄最新回 101 與連續等待次數；bad_runs／bad_exit 是一般 child 非零連敗次數與最新碼；aos_ticks 是連續觀察到 kind=aos 的完成次數。成功、等待或完成會清一般連敗；非 aos 會清 aos 連敗。

頂層 waiting 是**換下來的每個行程的計數表**，值為上述五個計數欄位的物件（允許省略尚未出現的欄）。即使行程沒有 waiting=true，仍存 bad_runs／aos_ticks；再次上 CPU 原樣取回。此處不存 runs_at／seen_runs，因那是 runner 的計數，不是行程的。done／bad／rm 會清掉該行程計數。

## 提交與持久化邊界

add 用 `aos_inst.load()` 解整份指示詞並驗完整 inst，轉成沒有指示詞的等價 v1 JSON，保留 clear／mkdir／append／inherit／merge，cwd／路徑固定為絕對路徑再入列。手工放入 procs 的 inst 在 tick 用相同方式讀驗與固定路徑，解析中心是該檔所在資料夾；不事先拒絕尚未存在的 executable 或有 mkdir 的 cwd。

syscall 名字為 `<epoch ns>-<pid>-<random 4 hex>.json`。回音先原子寫到 done，再刪原單；已有同名 done 就不再執行。rm 在 CPU 真正閒置時才換下，不截斷正在執行的一格；CLI 等回音最多 10 秒，逾時仍留單待辦。

JSON 用同目錄唯一暫存檔加 replace，沒有 fsync／跨檔交易；崩潰後不承諾自動對帳或 exactly-once。kernel state 與 daemon state 只有完成次數與最新退出碼，兩次 tick 之間多個結果會按最新碼計数；不保留每次結果歷史。done_exit 也可能在被觀察之前多跑幾次。這些限制沒有靠鎖假裝消失。

## slot 的讓位意圖

僅檢查 running 快照可能永久錯過兩次執行之間的間隔，尤其 interval_ms=0 或間隔短於 daemon 的採樣時間。因此 kernel 確定要輪轉、退休或 rm 時，先將既有 slot 鎖檔首 byte 寫成 `Y`（不換 inode、不等排他鎖、不影響已經開始的工作）。aos-run 每次取得 slot 排他鎖後、送 start 之前讀首 byte；看到 Y 就解鎖、可中斷地等候，既有工作照常完成。

running=true 的那格仍不換人。下一格有穩定的 running=false／slot 閒置狀態，kernel 拿鎖、等 remove 成功回音、保存新指派後，才在鎖內清空 Y，再啟動新 runner。remove 失敗保留意圖與原指派，下格重試；候選換人需求消失則非阻塞拿 slot 鎖後清空意圖。rm 待辦仍在時不取消其意圖。

這是一個 byte 的內部握手，沒有新增公開欄位、旗標或檔案。若 kernel 崩在寫 Y 之後，runner 可能停在兩格之間；重新 tick 會完成換人或清掉不再需要的意圖。鎖檔不可讀／寫會成為受控錯誤，不假裝已換人。
