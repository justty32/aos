← [kernel](README.md)｜[spec 總導航](../README.md)

## 1.3 kernel 取的檔名

（2026-09-24 proto5-2 池式納入：cpu 名改成 `P/<i>`、拿掉 `spawn`／`kill`／`stop` 的檔名、加 scale 單。原本在 [ledger.md](ledger.md) 末。2026-09-24 one-boot：kernel cpu 那格 tick 拿掉；加 boot 的登記單、停好時的撤登記單。）

| 放到哪 | 檔名 | 誰的 |
|---|---|---|
| 工作 cpu `P/<i>` 的 `requests/` | `k-<chain>-<seq>-<P>-<i>.json` | 第 seq 格派給那顆的工作 |
| 任一 cpu 的 `requests/` | `ack-<chain>-<seq>-<家名>-<digest>.json` | ack |
| daemon 的 `requests/` | `k-<chain>-<seq>-scale-<P>.json`（一格一池最多一張） | 池的宣告（[§3.1](pools.md)） |
| daemon 的 `requests/` | `k-<chain>-boot-scale-kernel-down.json` | 只有舊帳本：boot 把舊 kernel 池縮到 0（[§6 boot](boot.md)） |
| 開 tick 的 daemon 的 `requests/` | `k-<chain>-boot-tick.json` | boot 登記「請替我開 tick」（[§6 boot](boot.md)） |
| 開 tick 的 daemon 的 `requests/` | `k-<chain>-<seq>-untick.json` | 停好那格撤登記（notification，§3 第 9 步） |
| daemon 的 `requests/` | `ack-<chain>-<seq>-<家名>-<digest>.json` | 收完 scale 回音的 ack（boot 自己收的回音當場 ack，seq 寫 0） |

cpu 丟到 `K/requests/` 的通知叫 `resp-<digest>.json`（[cpu §6.4](../cpu/notify.md)），不是 kernel 取的。
CLI 放的照範式慣例 `cli-<epoch ns>-<pid>.json`。

kernel 放出去的檔名全部帶 `chain`，跨 boot 永不重複；同一格對同一個家的同一種東西最多一份，所以格內也不重複。
這是範式 §1「名字不重用」在 kernel 這邊的做法。前提是 `chain` 本身不重複——`<epoch ns>-<pid>` 在同一台機器上夠用。

ack 是例外：同格同家可能要好幾則（第 6 步收的、第 7 步收 scale 回音），所以 ack 名稱帶 digest，
digest 是**被 ack 的檔名**之 SHA-256 前 16 個十六進位字元。同格同家可以有多筆 ack，不得把不同回音的確認合併成一則。
出貨「送出後、清帳前」崩潰時，ack 重放用新一格的 seq 取名，同一則回音可能收到兩份不同名的 ack（第二份無害）。

注意 seq 沒補零：daemon 照檔名字典序處理單時 `-10-` 會排在 `-9-` 前面，先後靠 scale 單的 `decl` 分辨（[daemon §3](../daemon/methods.md)）。
