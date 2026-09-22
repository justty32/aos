# kernel 家（第 1 版）

← [README](../README.md)｜程式：[aos-kernel](aos-kernel.md)｜[inst](inst-posix.md)

> 這份是 proto5.1 做出來的版本（2026-09-22 回流，照 [23 題拍板](../notes/2026-09-22-decisions.md)）。**proto5 的程式還沒照這份實作**；能跑的實作在 [proto5.1/lib](../../proto5.1/lib/README.md)。

Kernel 排程的行程都是普通 posix inst；agent、llm cpu、tool cpu 沒有特別身分。沒有 module。

## 目錄

| 路徑 | 意義 |
|---|---|
| `info.json` | kernel 身分與排程設定 |
| `inst.json` | kernel 自己的 tick；cwd 是 K，argv 是 Python 與 `cli/aos-kernel tick` 的絕對路徑 |
| `idle.json` | 固定的無副作用 inst，閒置 CPU 指向這份檔 |
| `state.json` | 原子替換的排程快照，見下 |
| `procs/<NAME>.json` | 行程的完整 posix inst；排上 CPU 後仍留在這裡 |
| `procs/done/<NAME>.json` | 回 done_exit 的行程 |
| `procs/bad/<NAME>.json` | 無法讀驗、連敗或 aos 執行錯誤的行程 |
| `cpus/<N>.json` | 指向 `procs/<NAME>.json` 的 symlink；N 從 0 起。閒置時指向固定的 `K/idle.json` |
| `.kernel.lock` | tick／add 的 flock，保護 state 與檔案指派；重疊 tick 直接退 0 |
| `syscalls/<單名>.json` | 唯一 syscall：`{"op":"rm","name":"NAME"}` |
| `syscalls/done/<單名>.json` | 成功 `{"ok":true,"msg":"removed NAME"}`；失敗 `{"ok":false,"code":"代號","msg":"白話"}` |
| `kernel.log` | 每格 append 排程／退件記錄；tick stderr 也 append 於此 |

不同 CPU 不得同時指派同一 NAME，queue 內也不能重複。NAME 是非空檔名，不能是 `.`／`..` 或含 `/`／NUL。自動名字為所有 active／done／bad 數字名最大值加 1。具名 add 不覆蓋任何已存在名字；rm 能移除 active／done／bad。

CPU 檔一律用同目錄臨時 symlink 加 rename 替換，連 idle 也一樣；runner 解析完後只會讀固定的實體檔，不會再次讀可能已換人的 CPU 路徑。行程的絕對路徑 `K/procs/NAME.json` 是 run.json 裡的 target 身分；不能靠 hardlink 反推出原路徑。指派與執行分開：檔案已換成 Y，runner 仍可能正在做上一個 X。

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
  "bad_after": 10,
  "kill_tree": false,
  "daemon": "/absolute/daemon-home"
}
```

daemon 由 boot 驗家後寫入絕對路徑；init 尚未 boot 時沒有這格。
tick／ls／rm 都讀這格，不再用環境變數選家；daemon 若有值，必須是絕對路徑字串。

最外層 daemon 是 boot 寫的字面綁定，讀取時優先採用，不解指示詞。
整份 info 用 `$ref` 時，boot 保留 `$ref` 並在最外層加 daemon；其他設定仍照引用讀。
最外層沒有 daemon 才從解開的 info 讀這格。

其他設定、整份 info、metainfo 及其中兩欄都解 [指示詞](directives.md)，中心路徑是 K。不提供 `$opt`；解完驗型別。ncpu 必填正整數，其他排程欄缺省如上。kill_tree 必須是布林；整數欄 bool 不是整數。interval_ms／timeout_ms／bad_after 可為 0，quantum 至少 1。done_exit 是 0～255（0 關閉完成判定），wait_exit 是 1～255，兩者不得相同。bad_after=0 關閉一般子程式連敗退件。

timeout_ms 只限制每顆工作 CPU 的一次執行，kernel 自己的 tick 不設 timeout。kill_tree 傳給 daemon add，決定 runner 的停止方式；詳細語意見 [aos-run](aos-run.md)。init 只吃 ncpu，其餘設定修改 info；ncpu 不應在有指派時縮小，超出範圍的 state 會被拒。已啟動 runner 的 interval／timeout／kill_tree 不熱更新；下次建立才採新值。

## state.json

```json
{
  "cpus": {
    "0": {"name":"one", "runs_at":3, "seen_runs":5,
          "waiting":false, "wait_runs":0, "bad_runs":2, "aos_ticks":0},
    "1": null
  },
  "queue": ["two"],
  "waiting": {"two":{"waiting":true,"wait_runs":1,"bad_runs":0,"aos_ticks":0}}
}
```

cpus 的 key 是 CPU 編號字串，null 表示 idle。name 是 kernel 行程 NAME，不是 Linux pid。

runs_at 是這次指派的 runner 完成次數基線，seen_runs 是已觀察結果的次數。換人不重建 runner，所以上 CPU 時從現有 runs 起算；若當下 busy，就把還在做的舊工作也排除，兩個基線設 runs+1。runner 缺少而需重建時基線才歸零。

waiting／wait_runs 記錄最新回 101 與連續等待次數；bad_runs 是一般 child 非零連敗次數；aos_ticks 是連續觀察到 kind=aos 的完成次數。成功、等待或完成會清一般連敗；非 aos 會清 aos 連敗。只要 run.json 的 last_target 對得上本行程且 runs 增加，就讀 last_* 算一次結果，busy=true 也能算；本次 target 與上次完成目標分開。

頂層 waiting 是換下來的行程計數表，值為上述四個計數欄位的物件（允許省略尚未出現的欄）。再次上 CPU 原樣取回；此處不存 runner 的 runs_at／seen_runs。done／bad／rm 會清掉該行程計數。

## 提交與持久化邊界

add 用 `aos_inst.load()` 解整份指示詞並驗完整 inst，轉成沒有指示詞的等價 v1 JSON，保留 clear／mkdir／append／inherit／merge，cwd／路徑固定為絕對路徑再入列。手工放入 procs 的 inst 在 tick 用相同方式讀驗與固定路徑，解析中心是該檔所在資料夾；
add 已固化的內容不用再寫，tick 只有讀驗後的固化內容跟原檔不同才重寫；不事先拒絕尚未存在的 executable 或有 mkdir 的 cwd。已指派的 procs 檔不重新入列。

syscall 名字為 `<epoch ns>-<pid>-<random 4 hex>.json`。回音先原子寫到 done，再刪原單；已有同名 done 就不再執行。rm 直接把 CPU 目標改為 idle 並移除行程檔，不等目前執行完、不送訊號；已讀進 inst 的工作照常完成。CLI 等回音最多 10 秒，逾時回 ReadFailed，仍留單待辦。

JSON 用同目錄唯一暫存檔加 replace，沒有 fsync／跨檔交易；崩潰後不承諾自動對帳或 exactly-once。run.json 只有完成次數與最新碼，兩次 tick 之間的多個結果無法逐次對應；計數每份新快照最多加一，不把 runs 差值都當成本行程的結果。last_target 讓 busy 期間也能對應上次完成，但 done／bad／wait 判定仍不保證捕捉兩次 tick 間每次結果，quantum 按 runs 推進。已換下者的遲到結果也不回填歷史。這些限制不影響同名行程不重疊的檢查。
