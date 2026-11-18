# aos-share：替共用夾與點名使用者的檔案設定 ACL

← [cmd](../../../docs/05-commands.md)｜出處：[kernel-limits-plan 08](../../../../thinking/2026-11/13/kernel-limits-plan/08-群組用法.md)

```sh
aos-share [--dry-run] KIND PATH (--group G | --uid U)...
aos-share team /shared/team --group sub:600
aos-share check [-R] [--list-acl] PATH...
aos-share reset [-R] [--dry-run] PATH...
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

## 體檢與退回：`check`、`reset`

出處：[sec-1114 10 第 1 期施工 1b](../../../../thinking/2026-11/14/sec-1114/10-第1期施工.md)。兩個子命令要寫在**第一個字**（`aos-share check …`）；寫在旗標後面（`aos-share --dry-run check …`）照舊當 KIND 看，報 `ArgumentsBad`，六種 KIND 的用法、輸出、錯誤代號都沒變。`-R`（＝`--recursive`）兩個都收：PATH 底下每一項也算，走的時候 symlink 跳過、不跟進去（PATH 本身是 symlink 就跟過去）。

`aos-share check [-R] [--list-acl] PATH...`：唯讀，一行一個問題，最後一行 `total: N`（N＝上面的行數）；N 大於 0 退 1，否則退 0。ACL 直接讀 `system.posix_acl_access`／`system.posix_acl_default`（getfacl 讀的同一份），不需要 getfacl。

| 行 | 什麼時候印 |
|---|---|
| `secret-open PATH mode=0644` | 普通檔、檔名是 `.env`、`*.env`、`token*`、`*token*.json`、`*.key`、`exec.json`、`*secret*`（分大小寫），或被這次掃到的某個 `tools.json` 的 `tools.*.env_file` 指到（相對路徑從那份 tools.json 的夾算；指示詞物件不算），而且 group 或 other 有 r（看 mode 的 `044`） |
| `acl-masked PATH entry=u:ID:rwx effective=r--` | 有名字的 user／group 項目被 mask 壓掉一部分；預設 ACL 的寫成 `entry=d:u:…`。一個項目一行 |
| `acl-missing PATH (parent has default ACL)` | 父夾的預設 ACL 有命名項目或 mask，這一項卻沒有擴充 ACL（多半是 `mv` 進來的） |
| `acl-present PATH` | 只在 `--list-acl` 時印：有擴充 ACL 或預設 ACL 的項目，給 `reset` 前後比對 |
| `unreadable PATH ERRNO` | 看不到這一項（例 `ENOENT`、`EACCES`；列不出內容的夾、讀不到的 tools.json 也算） |

`aos-share reset [-R] [--dry-run] PATH...`：把樣板退回去。每個 PATH 依序跑 `setfacl [-R] -b PATH`（清掉擴充與預設 ACL），PATH 是夾就再跑 `chmod g-s,-t PATH`；加 `-R` 時底下每個夾也各跑一次 `chmod g-s,-t`。rwx 位不動，所以 `secret-open` 要自己 `chmod 600`。`--dry-run` 每步只印 argv（空白相接），不改東西、不檢查 PATH 在不在；真的做時 PATH 不在＝`PathMissing`，沒有 setfacl＝`CommandMissing`，某一步失敗＝`AclFailed`。重跑結果不變。

產權不在這裡還原。換過 uid 的 proc 寫出來的檔，退回的第二步是跑 `aos-asuser --fix --recursive PATH`（它自己開 userns，用裡面的 0 把產權改回使用者；見 [aos-asuser](../asuser/README.md)）。

測試：`python3 -m unittest discover -s proto8/py/tests/apps/share`（`test_share.py` 是六種樣板，`test_check_reset.py` 是 check／reset；需 `setfacl/getfacl`；可用 `KERNEL_TEST_TMP` 指定暫存夾的父夾；無法替外部 id 設 ACL 的環境會略過真 ACL 例子）。

新指令重新 `source "$AOS_HOME/env.sh"` 就在 PATH 上。

daemon 起換了 uid 的 proc 前會自己替它的 stack 設 G6 那組 ACL（daemon 段 3，C++，還沒做）；這支給手動與共用夾用。
