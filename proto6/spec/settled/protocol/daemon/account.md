# daemon 協議：帳號模組

← [daemon 協議](README.md)｜行為：[B-646](../../daemon/account.md)｜[慣例](../../conventions.md)

## P-126：帳號模組：設定、root 端封包與輸出

schema：`daemon-core-config.schema.json` 的 `modules.account` 與 `$defs/Item.account`；範例 `examples/daemon/core-config.account*`。程式：`aos_daemon_account.py`、`aos_daemon_root.py`。

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
| `.user` | 字串，可省 | 預設帳號；省＝環境變數 `SUDO_USER` |
| `.allow`／`.deny` | 非空字串陣列，預設 `[]` | 白／黑名單：完整帳號名，或結尾一個 `*` 當前綴（單獨 `*`＝全部）；`*` 不能在別處 |
| `insts.<inst>.account.user` | 字串，可省 | 該項帳號名（不收 UID）；省＝預設帳號；模組沒掛時 `account` 忽略 |

名單准不准、帳號查不查得到是執行時核的，schema 驗不到。

**root 端**：`<bin>/aos-daemon-root <fd>` 是內部程序（不給人或任務用），主程式開起來時（還是 root）開它，交一頭 `AF_UNIX`／`SOCK_SEQPACKET` socketpair。一個封包一則 UTF-8 JSON：

| 方向 | 內容 |
|---|---|
| 主→root，第一則 | `{"default":"<預設帳號>","allow":[…],"deny":[…]}` |
| 主→root，請求 | `{"id":<整數>,"user":"<帳號>","argv":[…],"cwd":"<絕對路徑>","env":{…},"frame":"<框的絕對路徑>"或null}`，附兩個 fd（`SCM_RIGHTS`）：子程序的 stdout、stderr；stdin 是 `/dev/null` |
| 主→root，送訊號 | `{"signal":<請求 id>,"final":false\|true}`（`false`＝SIGTERM、`true`＝SIGKILL；不認得的 id 不做事；不回應） |
| root→主，結束 | `{"id":<同一個>,"exit":<碼>}`（訊號 N＝128+N） |
| root→主，開不了 | `{"id":<同一個>,"error":"no such user <帳號>"}`，或 `"not allowed: <帳號>"`、`"not allowed: <帳號> is root"` |

子程序 exec 前出錯：它的 stderr 寫 `aos-daemon-root: <說明>`、以 127 結束。主程式那頭關了，root 端回 0 退出、不殺還在跑的子程序。

**stderr 與結束碼**：

| 什麼時候 | daemon 的 stderr | 結果 |
|---|---|---|
| 開起來：沒用 root、沒有預設帳號、預設帳號查不到或是 root、名單寫錯、`deny` 比到預設帳號、某項帳號不准或查不到 | `aos-daemon: account: <說明>` | 回 1 |
| 重讀：某項帳號不准或查不到 | `aos-daemon: reload: <說明>` | 整份不套用、照跑 |
| root 端回 `error` | `aos-daemon: account: <error 內容>` | 該次 `exit=1`，照跑 |
| root 端不見了 | `aos-daemon: account: root 端不見了` | 刪 socket 檔、回 1 |

stdout 不多印任何行。
