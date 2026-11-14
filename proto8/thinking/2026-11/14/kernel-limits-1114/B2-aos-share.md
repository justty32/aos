# 圖紙 B2：aos-share——替共用夾設 ACL 的小指令（線限 11-14，照 kernel-limits-plan 段 3「aos-share」與 08 的 G1～G6）

← [線限 11-14 紀錄](../kernel-limits-1114.md)｜設計出處：[08 群組用法](../../13/kernel-limits-plan/08-群組用法.md)（用法表與「一個 daemon 一個群組」那節）、[06 試驗 X14～X37](../../13/kernel-limits-plan/06-試驗紀錄.md)

施工隊照這份寫碼，不做設計決定。圖紙沒寫到、或自相矛盾＝BLOCKED。

## 0. 範圍（只准動這些檔）

- 新增 `proto8/cmd/aos-share/bin/aos-share`（Python 3，可執行，`#!/usr/bin/env python3`）
- 新增 `proto8/cmd/aos-share/README.md`
- 新增 `proto8/cmd/aos-share/tests/test_share.py`

風格照 `proto8/cmd/aos-tree-start/`（同樣的 `aos_flags` import 寫法、HELP 字串、`die`、退出碼慣例）。程式輸出一律英文；註解繁體中文；檔頭第一行（shebang 之後）一句話。

## 1. 為什麼有這支（背景）

換了 subuid 的 agent（`sub:N`＝真 uid `subuid 起點 + N - 1`）跟使用者不同 uid。要它們共用某個夾，靠使用者在自己的夾上寫 ACL（使用者寫別的 uid／gid 的 ACL 不用 root）。普通用途**一台 daemon 一個群組**：同台的 agent 主群組都是那台的群組。這支把六種樣板包成指令，使用者自己跑。

## 2. 用法

```
aos-share [--dry-run] KIND PATH (--group G | --uid U)...
aos-share --help
```

- `G`、`U` 寫成 `sub:N`（N 是 1～65536 的十進位整數）＝換成真號：`--uid` 用 `/etc/subuid`、`--group` 用 `/etc/subgid` 裡**目前使用者**那一行（`名字:起點:個數`，名字比 `pwd.getpwuid(os.getuid()).pw_name`；也接受那一行第一欄是數字 uid）。真號＝`起點 + N - 1`；`N > 個數`＝錯。寫成純數字＝照字面當真號。
- 每種 KIND 需要的旗標（多給別種＝`ArgumentsBad`，少給＝`ArgumentsBad`）：

| KIND | 用法（08 編號） | 旗標 | 做什麼（ME＝目前使用者的真 uid） |
|---|---|---|---|
| `team` | G1 共寫夾 | `--group` 剛好一個 | `mkdir -p PATH`；`chmod 2770 PATH`；`setfacl -m g:G:rwx,d:g:G:rwx,d:u:ME:rwx,m::rwx,d:m::rwx PATH` |
| `read` | G2 唯讀分享夾 | `--group` 一個以上 | PATH 必須已存在；每個 G：`setfacl -R -m g:G:rX PATH` 與 `setfacl -R -d -m g:G:rX PATH`（`-d` 只對夾有效，setfacl 自己會略過檔）；最後 `setfacl -R -m m::rwX PATH` |
| `key` | G3 金鑰門（點名 uid） | `--uid` 一個以上 | PATH 必須是已存在的普通檔；`chmod 600 PATH`；每個 U：`setfacl -m u:U:r PATH`；最後 `setfacl -m m::r PATH` |
| `work` | G4 可改不可刪 | `--group` 剛好一個 | 同 `team`，但 `chmod 3770` |
| `drop` | G5 投遞箱 | `--group` 剛好一個 | `mkdir -p PATH PATH/tmp PATH/new PATH/cur`；PATH、`PATH/tmp`、`PATH/new` 三個各：`chmod 1730`、`setfacl -m g:G:wx,m::wx X`、`setfacl -d -m u:ME:rwX,g::---,o::---,m::rwX X`（大寫 X：寄件人建的信夾收件人進得去；mask 用 wx，`stat` 才看得到 1730）；`PATH/cur`：`chmod 700`（不加 ACL） |
| `stack` | G6 agent 的 stack | `--uid` 剛好一個 | `mkdir -p PATH`；`chmod 700 PATH`；`setfacl -m u:U:rwx,d:u:U:rwx,d:u:ME:rwx,m::rwx,d:m::rwx PATH` |

- 指令一律用 `subprocess.run([...], capture_output=True, text=True)` 跑真的 `chmod`／`setfacl`（照 PATH 找；`mkdir -p` 與 `chmod` 可以改用 `os.makedirs(..., exist_ok=True)`／`os.chmod`，結果要一樣）。
- 同樣的指令跑第二次結果不變（冪等）。
- `--dry-run`：什麼都不改，每一步印一行到 stdout，格式是那一步的 argv 用空白接起來（例 `setfacl -m g:100600:rwx,d:g:100600:rwx,d:u:1000:rwx,m::rwx,d:m::rwx /x/team`；`mkdir -p`、`chmod` 也照這個形狀印，即使實作用的是 os 函式）。`--dry-run` 下也不檢查 PATH 存不存在，但 `sub:N` 照樣要換號（錯照報）。
- 成功：stdout 不印東西（`--dry-run` 除外），退 0。

## 3. 祖先檢查（警告，不擋）

真的做完之後，對 PATH 的每一層祖先夾（從 `/` 到 PATH 的父夾，用 `os.path.realpath(PATH)` 算）看權限位：「別人」沒有 x（`mode & 0o001 == 0`）而且 `getfacl -n --omit-header --absolute-names -c <夾>` 的輸出裡沒有一行以 `group:<G>:` 或 `user:<U>:` 開頭、權限有 `x` 的（G／U 是這次的號；那行有 `#effective:` 就看它後面的權限，沒有就看第三欄），就 stderr 印一行：

`aos-share: warning: <夾> gives no x to others: uid/gid <號> cannot reach <PATH>`

每個（夾, 號）最多印一次。`--dry-run` 不做這段。

## 4. 錯誤（stderr 一行 `aos-share: error: CODE reason`，退 1）

| CODE | 什麼時候 | reason 例 |
|---|---|---|
| `ArgumentsBad` | KIND 不認得、少 PATH、旗標配不上 KIND、`sub:N` 寫壞 | `KIND must be one of team, read, key, work, drop, stack` |
| `FlagUnknown` | 不認得的旗標 | 照 aos_flags 慣例 |
| `SubidMissing` | `/etc/subuid`／`/etc/subgid` 讀不到、沒有目前使用者那一行、N 超過個數 | `no line for lorkhan in /etc/subgid` |
| `PathMissing` | `read`／`key` 的 PATH 不在；`key` 的 PATH 不是普通檔 | `/x/key.txt does not exist` |
| `CommandMissing` | PATH 上沒有 `setfacl`（或 `getfacl`） | `setfacl not found on PATH` |
| `AclFailed` | `setfacl`／`chmod` 退非 0 | `setfacl -m ... /x failed: <它的 stderr 第一行>` |

## 5. README.md

照 `proto8/cmd/aos-tree-start/README.md` 的格式：標題一行、`← [cmd](../README.md)｜出處：[kernel-limits-plan 08](../../thinking/2026-11/13/kernel-limits-plan/08-群組用法.md)`、一個用法區塊、第 2 節那張表（中文）、第 3 節一句、第 4 節錯誤代號列一行、測試怎麼跑一行、「新指令要跑一次 `proto8/install.sh` 才會出現在 `~/.local/bin`」一句。加一句：「daemon 起換了 uid 的 proc 前會自己替它的 stack 設 G6 那組 ACL（daemon 段 3，C++，還沒做）；這支給手動與共用夾用。」

## 6. 測試 tests/test_share.py

- `unittest`；在 `tempfile.mkdtemp(dir=os.environ.get("SHARE_TEST_TMP"))` 底下做（預設 `/tmp`）；真跑的例子（下面 1～5、8）開頭先試 `setfacl -m g:200599:r <暫存檔>`，不成功就 `skipTest("cannot set ACLs for foreign ids here")`——施工隊的 bwrap 沙箱是 user ns，裡面對不到 200599 這種號，setfacl 會報 Invalid argument，所以這幾例在沙箱裡會 skip，由隊長在沙箱外跑；`--dry-run` 與錯誤那幾例（6、7）不需要 ACL，沙箱裡也要過。
- 假的 subid 檔：程式要支援環境變數 `AOS_SHARE_SUBUID`、`AOS_SHARE_SUBGID`（給了就讀那個檔，不讀 `/etc/...`）；測試寫一份 `<使用者名>:200000:65536` 進去用。README 註明這兩個變數只給測試用。
- 至少要有：
  1. `team` 真跑：`getfacl` 看得到 `group:200599:rwx`（`sub:600`）、`default:group:200599:rwx`、`default:user:<ME>:rwx`；`stat` 權限是 `2770`。跑第二次 `getfacl` 輸出不變。
  2. `drop`：四個子夾在、`new` 的權限 `1730`、預設 ACL 有 `default:group::---` 與 `default:user:<ME>:rwX`（getfacl 印成 `rwx`）；`cur` 是 `700`；在 `new` 裡 `os.mkdir` 一個子夾，它的 ACL 有 `user:<ME>:rwx` 而且沒有 `#effective:` 把 x 遮掉。
  3. `key`：`getfacl -n` 有 `user:200004:r--`（`--uid sub:5`）、`group::---`、`mask::r--`、`other::---`；`stat` 權限是 `640`（有 ACL 時 stat 的群組位就是 mask）。
  4. `read` 兩個 `--group`：兩個 group 項都在，子夾的預設 ACL 也有。
  5. `stack`：`user:200004:rwx` 與 `default:user:<ME>:rwx`、`group::---`、`other::---`；`stat` 權限是 `770`（同上，群組位＝mask）。
  6. `--dry-run team`：stdout 的行與第 2 節的步驟一一對得上、夾沒被建。
  7. 錯：KIND 不認得、`team` 給了 `--uid`、`sub:0`、subgid 檔沒有這個使用者、`key` 的 PATH 不在，各一例，比對退出碼 1 與 CODE。
  8. 祖先警告：在暫存夾裡建一層 `chmod 700` 的夾 A，`team A/B --group sub:600` → stderr 有 `gives no x to others` 而且點名 A。
- 跑法（必須全綠）：`python3 -m unittest discover -s proto8/cmd/aos-share/tests`

## 7. Argon 審後的補充（11-14 ok-limits；跟上面衝突時以這節為準）

- `/etc/subuid`、`/etc/subgid`（或測試用檔）解析：空行與 `#` 開頭的行略過；同一使用者多行取第一行。`sub:N` 的 N 與純數字的真號都不准前導 0、正負號、空白。
- 有 ACL 的檔：`stat` 的群組位顯示的是 `mask::`，所以測試一律以 `getfacl -n` 的項目為準，`stat` 只在第 6 節點名的地方驗。
- 投遞箱的寄件端建檔／建夾要給群組位（例 `0660`／`0777`），否則 mask 會被交集成 `---`、收件人讀不到；aos-post 建信夾用 `mkdir(..., 0777)`，沒問題。README 的 `drop` 那列加這一句。
