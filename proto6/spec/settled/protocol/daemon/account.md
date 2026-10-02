# daemon 協議：帳號模組的設定、root 端封包與輸出

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-646](../../daemon/account.md)｜[慣例](../../conventions.md)

本篇只有 P-126，只寫格式。預設帳號怎麼定、名單怎麼判、誰開哪一項，以 [B-646](../../daemon/account.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十三批：帳號模組」](../../../../notes/verdicts/11-tick-as-unit/15-1001-第十三批.md#2026-10-01-第十三批帳號模組)、[plan m3m 模組五](../../../../plan/m3m-daemon-modules/06-模組五-帳號.md#模組五帳號modulesaccount)；現行程式 [帳號](../../../../src/py/README.md#帳號m3m-模組五)（有出入以程式為準）。

## P-126．帳號模組：設定、root 端封包與輸出〔使用者 2026-10-01 第十二、十三批；格式照現行程式〕

### 設定

daemon 設定檔（[P-120](core.md)）頂層 `modules` 裡寫 `account`，每一項的帳號寫在 `insts` 那一項的 `account` 鍵：

```json
{
  "interval_ms": 60000,
  "modules": {"account": {"user": "lorkhan", "allow": ["agent-*", "bob"], "deny": ["agent-admin"]}},
  "insts": {
    "a.json": {},
    "/srv/bob-job": {"account": {"user": "bob"}},
    "/srv/agents/1.json": {"account": {"user": "agent-1"}}
  }
}
```

| 位置 | 型別 | 意思 |
|---|---|---|
| `modules.account` | 物件 | 有寫就開；要用 root 開 daemon |
| `modules.account.user` | 字串，可省 | 預設帳號；省了用環境變數 `SUDO_USER` |
| `modules.account.allow` | 非空字串的陣列，可省，預設 `[]` | 白名單：完整帳號名，或結尾一個 `*` 當前綴（單獨 `*`＝所有帳號）；`*` 不能在別處 |
| `modules.account.deny` | 同上 | 黑名單 |
| `insts.<inst>.account` | 物件，可省 | 模組掛著時這一項用哪個帳號；模組沒掛時照「不認得的鍵」忽略 |
| `insts.<inst>.account.user` | 字串，可省 | 帳號名（不收 UID 數字）；省了＝預設帳號 |

schema 見 [daemon-core-config](../../../protocol/schemas/daemon-core-config.schema.json) 的 `modules.account` 與 `$defs/Item` 的 `account`。範例：[掛帳號模組](../../../protocol/examples/daemon/core-config.account.valid.json)；反例：[`*` 在中間](../../../protocol/examples/daemon/core-config.account-star-middle.invalid.json)、[user 寫成數字](../../../protocol/examples/daemon/core-config.account-user-number.invalid.json)。名單准不准、帳號查不查得到、`deny` 比不比得到預設帳號是執行時核的，schema 驗不到。

### root 端

`<bin>/aos-daemon-root <fd>`：主程式開起來時（還是 root）開它、交一頭 `AF_UNIX`／`SOCK_SEQPACKET` 的 socketpair（`<fd>` 是它在 root 端的編號），另開一個 session。這是 aos 內部的封包，不是給人或任務用的介面。一個封包一則 UTF-8 JSON：

| 方向 | 內容 |
|---|---|
| 主程式→root 端，第一則 | `{"default":"<預設帳號>","allow":[…],"deny":[…]}` |
| 主程式→root 端，請求 | `{"id":<整數>,"user":"<帳號>","argv":[…],"cwd":"<絕對路徑>","env":{…},"frame":"<框的絕對路徑>"或null}`，附兩個 fd（`SCM_RIGHTS`）：子程序的 stdout、stderr。stdin 是 `/dev/null` |
| 主程式→root 端，送訊號〔第十九批〕 | `{"signal":<請求 id>,"final":false\|true}`：控制模組 `kill`／`restart` 用。對那個請求開的子程序（`aos-exec`）照 [B-641](../../daemon/control.md)「kill 與 restart」的規則送 SIGTERM（`final:false`）或 SIGKILL（`final:true`）；已經結束或不認得的 id 不做事；不回應 |
| root 端→主程式，結束 | `{"id":<同一個>,"exit":<碼>}`；被訊號 N 殺是 128+N |
| root 端→主程式，開不了 | `{"id":<同一個>,"error":"no such user <帳號>"}`，或 `"not allowed: <帳號>"`、`"not allowed: <帳號> is root"` |

- 子程序在 exec 之前出錯（切帳號、chdir、exec 失敗）：在它的 stderr 寫一行 `aos-daemon-root: <說明>`、以 127 結束。
- root 端讀到主程式那頭關了就回 0 退出，不殺還在跑的子程序。它忽略 SIGINT、SIGHUP。

### stderr 與結束碼

| 什麼時候 | daemon 的 stderr | 結果 |
|---|---|---|
| 開起來時：沒用 root 開、沒有預設帳號、預設帳號查不到或是 root、名單寫錯、`deny` 比到預設帳號、某項帳號名單不准或查不到 | `aos-daemon: account: <說明>` | 回 1（[P-120](core.md)） |
| 重讀設定時：某項帳號名單不准或查不到 | `aos-daemon: reload: <說明>`（[P-122](reload.md)） | 整份不套用、照跑 |
| root 端回 `error`（例如開起來之後帳號被刪） | `aos-daemon: account: <error 的內容>` | 那一次 `exit=1`，照跑 |
| root 端不見了 | `aos-daemon: account: root 端不見了` | 刪 socket 檔、回 1 |

stdout 不多印任何行；控制、訊息 socket 檔權限 666。

依據：使用者 2026-10-01 第十二、十三批；plan m3m 模組五。
