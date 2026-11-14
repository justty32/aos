# aos-share：替共用夾與點名使用者的檔案設定 ACL

← [cmd](../README.md)｜出處：[kernel-limits-plan 08](../../thinking/2026-11/13/kernel-limits-plan/08-群組用法.md)

```sh
aos-share [--dry-run] KIND PATH (--group G | --uid U)...
aos-share team /shared/team --group sub:600
aos-share --help
```

`sub:N`（1～65536）按目前使用者在 `/etc/subuid`（`--uid`）或 `/etc/subgid`（`--group`）的第一筆範圍換號：起點加 N 減一，N 不可超過個數；第一欄可用使用者名稱或數字 uid。空行與 `#` 開頭的行略過。純數字照字面當真號；兩種寫法都不可有前導零、正負號或空白。`AOS_SHARE_SUBUID`、`AOS_SHARE_SUBGID` 可指定替代檔，**只給測試用**。

| KIND | 用法 | 旗標 | 做什麼（ME＝目前使用者真 uid） |
|---|---|---|---|
| `team` | G1 共寫夾 | `--group` 剛好一個 | `mkdir -p PATH`；`chmod 2770 PATH`；`setfacl -m g:G:rwx,d:g:G:rwx,d:u:ME:rwx,m::rwx,d:m::rwx PATH` |
| `read` | G2 唯讀分享夾 | `--group` 一個以上 | PATH 必須已存在；每個 G 跑 `setfacl -R -m g:G:rX PATH`、`setfacl -R -d -m g:G:rX PATH`（預設 ACL 只對夾）；最後 `setfacl -R -m m::rwX PATH` |
| `key` | G3 金鑰門 | `--uid` 一個以上 | PATH 必須是已存在的普通檔；`chmod 600 PATH`；每個 U 跑 `setfacl -m u:U:r PATH`；最後 `setfacl -m m::r PATH` |
| `work` | G4 可改不可刪 | `--group` 剛好一個 | 同 `team`，但 `chmod 3770`（sticky bit） |
| `drop` | G5 投遞箱 | `--group` 剛好一個 | 建立 PATH 與 `tmp/new/cur`；PATH、`tmp`、`new` 各設 `chmod 1730`、`setfacl -m g:G:wx,m::wx`、`setfacl -d -m u:ME:rwX,g::---,o::---,m::rwX`；`cur` 只設 `chmod 700`。寄件端建檔／建夾要給群組位（例 `0660`／`0777`），否則 mask 交集成 `---`，收件人讀不到；aos-post 用 `mkdir(..., 0777)`，沒問題。 |
| `stack` | G6 agent 的 stack | `--uid` 剛好一個 | `mkdir -p PATH`；`chmod 700 PATH`；`setfacl -m u:U:rwx,d:u:U:rwx,d:u:ME:rwx,m::rwx,d:m::rwx PATH` |

每種樣板重跑結果不變。`--dry-run` 每步只印 argv（空白相接），不改東西、不檢查 PATH 是否存在，但仍解析 `sub:N`。成功不印 stdout（dry-run 除外），退 0。

真的做完後，從 `/` 到 PATH 父夾逐層檢查：others 沒有 x，且這次點名的 uid／gid 也沒有有效 ACL x，就印一行警告（不擋）；dry-run 不檢查。

錯誤代號：`ArgumentsBad`、`FlagUnknown`、`SubidMissing`、`PathMissing`、`CommandMissing`、`AclFailed`；stderr 一行 `aos-share: error: CODE reason`，退 1。

測試：`python3 -m unittest discover -s proto8/cmd/aos-share/tests`（需 `setfacl/getfacl`；可用 `KERNEL_TEST_TMP` 指定暫存夾的父夾；無法替外部 id 設 ACL 的環境會略過真 ACL 例子）。

新指令要跑一次 `proto8/install.sh` 才會出現在 `~/.local/bin`。

daemon 起換了 uid 的 proc 前會自己替它的 stack 設 G6 那組 ACL（daemon 段 3，C++，還沒做）；這支給手動與共用夾用。
