# daemon 協議：收屍／cgroup 模組

← [daemon 協議](README.md)｜行為：[B-644](../../daemon/cgroup.md)｜[慣例](../../conventions.md)

## P-124：收屍／cgroup：設定、框名與輸出

schema：`daemon-core-config.schema.json` 的 `modules.cgroup` 與 `$defs/Item.cgroup`；範例 `examples/daemon/core-config.cgroup*`。程式：`aos_daemon_cgroup.py`。

```json
{
  "interval_ms": 60000,
  "modules": {"cgroup": {}},
  "insts": {
    "a": {"cgroup": {"memory.max": "512M", "cpu.max": "50000 100000", "pids.max": "200"}},
    "b": {}
  }
}
```

| 位置 | 型別 | 意思 |
|---|---|---|
| `modules.cgroup` | 物件 | 有寫就開，沒有鍵；子樹根就是 daemon 自己所在的 cgroup |
| `insts.<inst>.cgroup` | 物件，可省 | 鍵＝cgroup 檔名（`memory.max`、`cpu.max`、`pids.max`…），值＝字串，原樣寫進該項的框；省＝不設限；模組沒掛時忽略 |

**框**：根 `<根>`＝daemon 開起來時所在的 cgroup（框名叫 `daemon` 時取上一層）。`<根>/daemon` 是 daemon 自己；`<根>/i-<h>` 一項一個葉框，`<h>`＝inst 字面值 UTF-8 的 sha256 前 16 個小寫 hex。根的 `cgroup.subtree_control` 開 `cpu`、`memory`、`pids` 中根的 `cgroup.controllers` 有的。

**stdout**（格式同 [P-120](core.md)）：

| 什麼時候 | 內容 |
|---|---|
| 開框（開起來每項一行；重讀加的項在 `added` 之後） | `inst=<inst> cgroup=i-<h>` |
| 一次跑完、框裡有殘留被清掉 | `inst=<inst> reaped`（在該次 `exit=` 行之後；沒殘留不印） |

**錯誤**：開起來時沒有委派好的 cgroup v2、建框或寫上限失敗＝traceback、回 1；重讀時失敗＝`aos-daemon: reload: <說明>`、不退出（[P-122](reload.md)）。
