# daemon 協議：收屍／cgroup 模組

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-644](../../daemon/cgroup.md)｜[慣例](../../conventions.md)

本篇只有 P-124，只寫格式。框怎麼建、何時清，以 [B-644](../../daemon/cgroup.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[plan m3m 模組二](../../../../plan/m3m-daemon-modules.md#模組二收屍與資源上限modulescgroup)；現行程式 [收屍／cgroup](../../../../src/py/README.md#收屍cgroupm3m-模組二)（有出入以程式為準）。

## P-124．收屍／cgroup：設定、框名與輸出〔使用者 2026-10-01 第十二批；格式照現行程式〕

### 設定

daemon 設定檔（[P-120](core.md)）頂層 `modules` 裡寫 `cgroup`，每一項的上限寫在 `insts` 那一項的 `cgroup` 鍵：

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
| `modules.cgroup` | 物件 | 有寫就開；裡面沒有鍵（寫了別的鍵照收不理）。子樹根就是 daemon 自己所在的 cgroup，不另外設 |
| `insts.<inst>.cgroup` | 物件，可省 | 鍵＝cgroup 檔名（例如 `memory.max`、`cpu.max`、`pids.max`），值＝字串，原樣寫進那一項的框；省略＝不設限。模組沒掛時照「不認得的鍵」忽略 |

schema 見 [daemon-core-config](../../../protocol/schemas/daemon-core-config.schema.json) 的 `modules.cgroup` 與 `$defs/Item` 的 `cgroup`。範例：[掛 cgroup、一項有上限](../../../protocol/examples/daemon/core-config.cgroup.valid.json)；反例：[上限的值寫成數字](../../../protocol/examples/daemon/core-config.cgroup-number.invalid.json)。

### 框

以 daemon 開起來時所在的 cgroup 為根 `<根>`（它所在的框名字是 `daemon` 時取上一層）：

| 路徑 | 是什麼 |
|---|---|
| `<根>/daemon` | daemon 自己（與開起來時根上的其他程序） |
| `<根>/i-<h>` | 一項一個葉框。`<h>`＝inst 字面值 UTF-8 bytes 的 sha256，取前 16 個小寫 hex |

根的 `cgroup.subtree_control` 開 `cpu`、`memory`、`pids` 裡根的 `cgroup.controllers` 有的那幾個。

### stdout

格式同 [P-120](core.md)：每行開頭是本地時間、空一格接內容。

| 什麼時候 | 內容 |
|---|---|
| 開框（開起來時每項一行；重讀設定加的項在 `added` 之後） | `inst=<inst 字面值> cgroup=i-<h>` |
| 一次跑完、框裡有殘留被清掉 | `inst=<inst 字面值> reaped`，在那次 `exit=` 行之後 |

```text
2026-10-01T17:07:03+08:00 inst=a.json cgroup=i-6025a12236ee54ba
2026-10-01T17:07:06+08:00 inst=a.json exit=0 ms=2032
2026-10-01T17:07:06+08:00 inst=a.json reaped
```

- `exit=` 行的 `ms` 算到 `aos-exec` 結束，不含清框的時間。
- 沒有殘留就不印 `reaped`。

### stderr 與結束碼

- 開起來時：沒有委派好的 cgroup v2、建框或寫上限失敗，照 Python 預設印 traceback、回 1（[P-120](core.md)「其他沒接住的錯」）。
- 重讀設定時建框、寫上限失敗：照 [P-122](reload.md) 印 `aos-daemon: reload: <說明>`，不退出。

依據：使用者 2026-10-01 第十二批（C1～C4 照 plan 建議）。
