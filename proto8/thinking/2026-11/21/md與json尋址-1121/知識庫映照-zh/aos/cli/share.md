# `knowledge/aos/cli/share.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/share.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-share：替指名的使用者在共用資料夾或檔案上設定 ACL

它套用六種 ACL 範本之一（`mkdir`、`chmod`、`setfacl`），讓另一個群組 id 或使用者 id，例如用 sub-id 跑的 agent，可以使用某個路徑。它是真的改權限：先用 `--dry-run` 跑。

```sh
aos-share --dry-run team /shared/team --group sub:600   # prints each command, changes nothing
aos-share team /shared/team --group sub:600
```

`aos-share [--dry-run] KIND PATH (--group G | --uid U)...`；旗標可以放在任何位置。

另外兩個子指令，必須是第一個字：

- `aos-share check [-R] [--list-acl] PATH...` 什麼都不改：每個發現一行（`secret-open` 機密檔案，例如 `.env`、`*.key` 或 `exec.json`，群組或其他人讀得到；`acl-masked` mask 砍掉了某條指名的 ACL 項目；`acl-missing` 上層有預設 ACL，但這裡沒有延伸 ACL；`acl-present` 有任何 ACL，只在 `--list-acl` 時；`unreadable`），最後一行 `total: N`；N > 0 時結束碼 1。
- `aos-share reset [-R] [--dry-run] PATH...` 撤銷範本：`setfacl -b`，然後對資料夾 `chmod g-s,-t`；rwx 位元和擁有者不變。

`-R` 也涵蓋 PATH 底下的每個項目（略過符號連結）。

| KIND | 做出什麼 | 需要 |
|---|---|---|
| `team` | 群組可以寫的資料夾（不存在就建立） | 一個 `--group` |
| `work` | 像 `team`，加上 sticky bit | 一個 `--group` |
| `drop` | 一個有 `tmp`、`new`、`cur` 的投遞箱：群組可以放東西進去，但不能列出內容；在那裡放檔案或資料夾的人，必須用群組位元建立它（例如 0660 / 0777） | 一個 `--group` |
| `read` | 一個已存在的路徑，對那些群組唯讀，遞迴 | 一個或多個 `--group` |
| `key` | 一個已存在的一般檔案（設成 mode 600），那些使用者讀得到 | 一個或多個 `--uid` |
| `stack` | 一個私人資料夾（mode 700），跟一個使用者共用（不存在就建立） | 一個 `--uid` |

G 和 U 是單純的數字（真正的 id）或 `sub:N`（1 到 65536）：你在 `/etc/subgid`（`--group`）或 `/etc/subuid`（`--uid`）裡第一段範圍的第 N 個 id。不能有前導零或正負號。

成功時什麼都不印。真的跑完之後，它可能會為某個上層資料夾印出 `aos-share: warning: DIR gives no x to others: uid/gid N cannot reach PATH`；它不會修這個。`--dry-run` 不檢查 PATH 存不存在，但仍然會解析 `sub:N`。

錯誤（`aos-share: error: CODE reason`，結束碼 1）：`ArgumentsBad`（不認得的 KIND、該用 `--group` 的地方用了 `--uid` 或反過來、個數不對、id 不對）、`SubidMissing`（subid 檔案裡沒有你能用的行，或 N 超出範圍）、`PathMissing`（`read` 和 `key` 不建立 PATH；`key` 需要一般檔案）、`CommandMissing`（`setfacl` 或 `getfacl` 不在 PATH 上）、`AclFailed`（某一步失敗；前面做完的步驟保持做完）、`FlagUnknown`。
