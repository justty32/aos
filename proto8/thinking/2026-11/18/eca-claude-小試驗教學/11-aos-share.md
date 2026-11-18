這份是試驗 11 的照打教學：試 aos-share（替共用夾套 ACL 樣板、體檢、退回）在這台公司 WSL 能做到哪、缺什麼、裝好後預期怎麼用（HEAD `71df48e88`）。
← [目錄](README.md)

使用者原話：「11. aos-share也試試看，同樣」（同樣＝試 10 的做法：做不到就寫出缺的、模擬假設一下）

## 結論

- **它是什麼**：ACL（存取控制清單，像在門上多貼幾張「某某人也可以進」的名牌）的六種現成樣板。`aos-share read 夾 --group sub:5`＝把夾唯讀分給第 5 號 subgid（真號 100004）。另有 `check`（唯讀體檢）與 `reset`（撕掉名牌）。
- **六種**：`team` 共寫夾、`read` 唯讀分享、`key` 金鑰檔給點名的人讀、`work` 可改不可刪、`drop` 投遞箱、`stack` agent 的 stack 分給一個 uid。
- **跟 aos-asuser 的關係**：號碼算法一樣（起點＋N－1），`aos-share --group sub:5` 給的就是 `aos-asuser sub:5` 跑起來的那個身分；驗證「分享有效」要靠 aos-asuser 換身分去讀。產權救回（`--fix`）在 aos-asuser，不在這裡。
- **這台能跑的**：`--help`、全部參數檢查、六種樣板的 `--dry-run`、`reset --dry-run`、**`check` 整個能用**（它直接讀 xattr，不靠 getfacl）。檔案系統 ext4、**支援 ACL**（實測寫得進、`ls` 看得到 `+`）。
- **跑不了的**：真的套樣板與 `reset`（缺 `setfacl`，套件 `acl`）；換身分驗證（缺 `uidmap`，見 [10](10-aos-asuser.md)）。**使用者跑一行 `sudo apt install acl uidmap`** 兩樣都補上。不需要別的帳號（subuid 已有）。

## 前置逐項（實測，只查有沒有）

| 項目 | 查法 | 這台 |
|---|---|---|
| setfacl／getfacl | `command -v setfacl getfacl` | **沒有**（`apt-cache policy acl`：未裝） |
| 檔案系統 | `findmnt -no FSTYPE,OPTIONS -T ~` | `ext4 rw,relatime,discard,…`（ext4 預設開 ACL，選項裡不會寫） |
| 核心 | `zcat /proc/config.gz \| grep EXT4_FS_POSIX_ACL` | `=y` |
| xattr 讀寫 | python `os.getxattr(檔,"system.posix_acl_access")` | 沒 ACL 時 `[Errno 61] No data available`；用 `os.setxattr` 寫一份給自己的檔後讀得回來、`ls -l` 出現 `-rw-r--r--+` |
| subuid／subgid | `/etc/subuid`、`/etc/subgid` | 有 `100000:65536` |
| 換身分工具 | `command -v newuidmap` | **沒有** |

## 實測步驟（不用 setfacl）

先 `cd ~/aos-home && source env.sh`，再開一個練習夾 `mkdir -p /tmp/aos-ref && echo hello > /tmp/aos-ref/notes.txt`。

**1. 看說明**
```sh
aos-share --help | head -5
```
會看到：`aos-share - apply an ACL template to a shared folder or a named-user file` 與三種 usage。

**2. 主線的 dry-run：把參考夾唯讀分給 sub:5**
```sh
aos-share --dry-run read /tmp/aos-ref --group sub:5
```
會看到：
```
setfacl -R -m g:100004:rX /tmp/aos-ref
setfacl -R -d -m g:100004:rX /tmp/aos-ref
setfacl -R -m m::rwX /tmp/aos-ref
```
其他樣板一樣能看（實跑過）：`stack 夾 --uid sub:5` → `mkdir -p`、`chmod 700`、`setfacl -m u:100004:rwx,d:u:100004:rwx,d:u:1000:rwx,m::rwx,d:m::rwx`；`team 夾 --group sub:600` → gid `100599`、`chmod 2770`；`drop` 會建 `tmp/new/cur` 各設 `1730`、`cur` 設 `700`；`key 檔 --uid sub:5 --uid sub:6` → `chmod 600` 再各加 `u:…:r`。

**3. 真跑（缺 setfacl 的錯）**
```sh
aos-share read /tmp/aos-ref --group sub:5
```
會看到：`aos-share: error: CommandMissing setfacl not found on PATH`，退 1，什麼都沒動。

**4. 參數檢查**（各退 1，節錄 `error:` 後面）
- `aos-share read /tmp/aos-ref` → `ArgumentsBad flags do not match read (usage: …)`（`--uid` 配 `read`、`team` 給兩個 `--group` 也是這行）
- `aos-share bogus x --group 5` → `ArgumentsBad KIND must be one of team, read, key, work, drop, stack …`
- `--group sub:65537`／`sub:05`／`-5`／`games` → `ArgumentsBad invalid gid id 'games'`（只收數字或 sub:N，不收群組名）
- `aos-share read /tmp/nothere --group sub:5` → `PathMissing /tmp/nothere does not exist`
- `aos-share key /tmp/aos-ref --uid sub:5` → `PathMissing /tmp/aos-ref is not a regular file`
- `aos-share --dry-run check x` → `ArgumentsBad KIND must be one of …`（子命令要寫第一個字，文件有寫）
- `aos-share reset`／`aos-share check` → `ArgumentsBad expected at least one PATH …`

**5. 體檢 check（不需 getfacl，真能用）**
```sh
echo s > /tmp/aos-ref/.env && chmod 644 /tmp/aos-ref/.env && aos-share check -R /tmp/aos-ref
```
會看到：`secret-open /tmp/aos-ref/.env mode=0644`、`total: 1`，退 1。不加 `-R` 只看夾本身 → `total: 0`。不存在的路徑 → `unreadable /tmp/nothere ENOENT`。
我另用 python 直接寫 xattr 造了 ACL（不用照做），check 都認得：`acl-masked …/a.txt entry=u:100004:rw- effective=r--`、`acl-missing …/moved.txt (parent has default ACL)`（`mv` 進來的檔）、`--list-acl` 時的 `acl-present …`。

**6. 退回的 dry-run**
```sh
aos-share reset --dry-run -R /tmp/aos-ref
```
會看到：`setfacl -R -b /tmp/aos-ref`、`chmod g-s,-t /tmp/aos-ref`。拿掉 `--dry-run` → `CommandMissing setfacl not found on PATH`；路徑不在 → `PathMissing`。

**7. 測試**
```sh
cd $AOS_HOME && python3 -m unittest discover -s py/tests/apps/share
```
會看到：`Ran 29 tests … FAILED (errors=19)`，19 個都是 `FileNotFoundError: … 'setfacl'`（見最後一節第 1 條）。

## 要使用者自己用 sudo 跑的（沒實測）

```sh
sudo apt install acl uidmap
```
`acl` 給 setfacl／getfacl，`uidmap` 給換身分驗證。正式的分享夾若要放在 `/srv`（不在家目錄底下），另加（**推的**，repo 沒寫）：`sudo install -d -o $(id -un) -g $(id -gn) -m 700 /srv/aos-share`。

## 裝好後的主線：把參考夾唯讀分給另一隻 agent（預期，未實測）

情境：agent bob 用沙箱 `"user": "sub:5"` 跑，要讀你的參考資料、不能改。期望值取自 `test_share.py`。

**1. 先收緊再分享**
```sh
chmod -R go-rwx /tmp/aos-ref && aos-share read /tmp/aos-ref --group sub:5
```
預期：沒有輸出、退 0。`/tmp` 有 others x，不會有祖先警告。

**2. 看名牌貼上了**
```sh
getfacl -n /tmp/aos-ref /tmp/aos-ref/notes.txt
```
預期：夾有 `group:100004:r-x`、`default:group:100004:r-x`；檔有 `group:100004:r--`；`ls -l` 權限後面出現 `+`。重跑一次 `read`，getfacl 結果不變。

**3. 換身分驗證**
```sh
aos-asuser sub:5 -- cat /tmp/aos-ref/notes.txt           # 預期 hello
aos-asuser sub:5 -- sh -c 'echo x > /tmp/aos-ref/new'     # 預期 Permission denied（唯讀）
aos-asuser sub:6 -- cat /tmp/aos-ref/notes.txt           # 預期 Permission denied（沒點名的人）
```

**4. 體檢**
```sh
aos-share check -R --list-acl /tmp/aos-ref
```
預期：每項一行 `acl-present …`，`total: N`、**退 1**（見最後一節第 2 條）；不應有 `acl-masked`。

**5. 收回並驗證**
```sh
aos-share reset -R /tmp/aos-ref && getfacl -n /tmp/aos-ref && aos-asuser sub:5 -- cat /tmp/aos-ref/notes.txt
```
預期：reset 沒輸出；getfacl 只剩 `user::`、`group::`、`other::` 三行；sub:5 讀 → `Permission denied`；`check -R --list-acl` → `total: 0`。

**放家目錄底下會怎樣**：`aos-share read ~/某夾 --group sub:5` 預期照樣套上，但多一行 `aos-share: warning: /home/<你> gives no x to others: uid/gid 100004 cannot reach …`，sub:5 實際讀不到（家目錄 750）。

## 發現的問題／缺的東西（不修程式）

1. **測試在沒 setfacl 的機器上倒 19 支而不是 skip**：`test_check_reset.py` 的 `setUp` 探針只看退出碼，沒接 `FileNotFoundError`；連 `test_help_lists_subcommands`、`test_errors` 這種不需要 ACL 的也一起倒。README 寫「無法設 ACL 的環境會略過」，對不上。
2. **`check --list-acl` 把 `acl-present` 算進 total、退 1**：健康的分享夾列一下也是「有問題」，腳本不好拿退出碼判斷。
3. **缺兩個套件**：`acl`、`uidmap`；驗證分享一定要有第二個身分，只裝 acl 只能看 getfacl、證明不了讀得到。
4. **家目錄 750**：分享 `~` 底下的東西給 subuid 會警告且讀不到；正式用要放 `/srv` 之類，或使用者決定給 `~` 加一條 `u:100004:x`。
5. `reset` 只撕 ACL 與 setgid／sticky，rwx 位與擁有者不還原（文件有寫）；收回後還要 `chmod`／`aos-asuser --fix` 自己補。
6. `--group` 不收群組名，只收數字或 sub:N。
7. 文件：`knowledge/aos/cli/share.json` 有；`py/docs/05-commands.md` 沒列 share。
