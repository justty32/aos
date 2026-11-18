這份是試驗 10 的照打教學：試 aos-asuser（免 root 換成 subuid 跑程式）在這台公司 WSL 能做到哪、缺什麼、裝好後預期怎麼用（HEAD `71df48e88`）。
← [目錄](README.md)

使用者原話：「10. 試試看aos-asuser...這個沒辦法做的話就把缺的東西寫出來，大概模擬假設一下。」

## 結論

- **它是什麼**：`aos-asuser sub:N -- 程式` 開一個 user namespace（像給程式一張「假身分證」），把程式換成你的第 N 號 subuid 跑；外面看那個程式是另一個真 uid（起點＋N－1，這台 `sub:5`＝100004），碰不到你的家目錄。`--fix` 反過來把 subuid 寫出的檔改回你擁有。
- **跟 aos-sandbox 的關係**：沙箱設定 `"user": "sub:N"` 就是在 bwrap 前面接 `aos-asuser --env-all sub:N --`（實測 dry-run 看到）。`"user": "aos-run"` 是另一條路：`sudo -n -k /usr/local/bin/s6-setuidgid aos-run`，要 root 先建帳號。
- **這台能跑的**：`--help`、參數檢查、錯誤訊息全部實跑；dry-run 要先放一個假 `newuidmap` 才印得出來。測試 20 支通過、6 支 skip。
- **跑不了的**：真的換身分。缺 `newuidmap`／`newgidmap`（套件 `uidmap`）。**只要使用者跑一行 `sudo apt install uidmap`**，`sub:N` 這條就通；`/etc/subuid` 已經有 `guanyu:100000:65536`。
- `aos-run` 帳號那條另外缺：帳號、s6、sudoers 規則、`/srv/aos-run`。

## 前置逐項（實測，只查有沒有）

| 項目 | 查法 | 這台 |
|---|---|---|
| subuid／subgid 範圍 | `grep "^$(id -un):" /etc/subuid /etc/subgid` | **有**：`100000:65536` 兩邊都有 |
| 免 root 開 user ns | `unshare -U id` | **可以**：印 `uid=65534(nobody)…` |
| newuidmap／newgidmap | `command -v newuidmap` | **沒有**（`apt-cache policy uidmap`：未裝，有候選版） |
| bwrap | `command -v bwrap` | 有 `/usr/bin/bwrap` |
| s6-setuidgid、s6-softlimit | `ls -l /usr/local/bin/s6-*` | **沒有**（套件 `s6` 未裝） |
| 帳號 aos-run | `getent passwd aos-run` | **沒有**（退 2） |
| `/srv/aos-run` | `ls -ld /srv/aos-run` | **沒有** |
| sudoers 規則 | `sudo -n -l`、`ls /etc/sudoers.d` | 只有 `README`；`sudo -n -l` 回 `a password is required` |
| 家目錄權限 | `ls -ld ~` | `drwxr-x---`（750）＝換了身分的程式**進不了 ~** |

## 實測步驟（不用 root）

先 `cd ~/aos-home && source env.sh`。

**1. 看說明**
```sh
aos-asuser --help | head -3
```
會看到：`aos-asuser - run as a subuid without root, or recover files owned by subuids` 與 usage。

**2. 真跑一次（缺工具時的錯）**
```sh
aos-asuser sub:5 -- id -u
```
會看到：`aos-asuser: error: CommandMissing newuidmap not found on PATH`，退 1。**`--dry-run` 也一樣報這行**（見最後一節）。

**3. 參數檢查**
```sh
aos-asuser --dry-run sub:0 -- id ; aos-asuser --dry-run sub:5 id ; aos-asuser --bogus sub:5 -- id
```
會看到（各退 1）：
- `ArgumentsBad expected sub:N with N from 1 to 60000: 'sub:0' (usage: …)`（`sub:05`、`sub:60001` 同樣）
- `ArgumentsBad expected sub:N -- PROG [ARGS...] (usage: …)`（少了 `--` 或 `--` 後面沒程式）
- `FlagUnknown unknown flag --bogus (usage: …)`
- `aos-asuser --fix sub:5 -- x` → `ArgumentsBad --fix needs paths, not run-mode arguments …`
- `aos-asuser --fix --recursive /tmp/nothere` → `PathMissing /tmp/nothere does not exist`（路徑檢查比工具檢查早）

**4. dry-run 看對照表（放假 newuidmap 才印得出）**
```sh
mkdir -p /tmp/stub && printf '#!/bin/sh\nexit 1\n' > /tmp/stub/newuidmap && cp /tmp/stub/newuidmap /tmp/stub/newgidmap && chmod +x /tmp/stub/*
PATH=/tmp/stub:$PATH aos-asuser --dry-run --group sub:7 sub:5 -- id
```
會看到：
```
newuidmap PID 0 1000 1 5 100004 1
newgidmap PID 0 1000 1 7 100006 1
exec 5:7 id
```
意思：namespace 裡的 0＝你（1000），裡面的 5＝外面的 100004。`--fix --recursive .` 則印整段 `1 100000 65536` 與 `fix .`。不拿假工具真跑：會是 `NsFailed newuidmap: …`。

**5. 替代 subuid 檔（只給測試）**
```sh
printf 'someone:1:2\n' > /tmp/stub/nosub && AOS_ASUSER_SUBUID=/tmp/stub/nosub aos-asuser --dry-run sub:1 -- id
```
會看到：`SubidMissing no line for <你> in /tmp/stub/nosub`。範圍只有 10 個卻要 `sub:11` → `SubidMissing requested subuid or subgid exceeds the current user's range`。

**6. 沙箱的 `user` 欄位**
```sh
echo '{"user":"sub:5","rw":["/tmp/stub"]}' > /tmp/stub/sub.json && aos-sandbox --dry-run /tmp/stub/sub.json id | cut -c1-120
```
會看到：`["…/bin/aos-asuser", "--env-all", "sub:5", "--", "/usr/bin/bwrap", "--unshare-all", …`。拿掉 `--dry-run` → `aos-asuser: error: CommandMissing newuidmap not found on PATH`。
`"user":"aos-run"` 不論有沒有 dry-run → `aos-sandbox: error: UserBad unknown account aos-run`；`"user":"1001:1001"` → `UserBad uid:gid needs root; give an account name to go through sudo`。

**7. 測試**
```sh
cd $AOS_HOME && python3 -m unittest discover -s py/tests/apps/asuser
```
會看到：`Ran 20 tests … OK (skipped=6)`（6 支真換身分的 skip）。

## 要使用者自己用 sudo 跑的（沒實測）

**A. 只要 `sub:N` 這條（推薦，一行）**——套件名從 `apt-cache policy uidmap` 查到：
```sh
sudo apt install uidmap
```
裝完自己查：`ls -l /usr/bin/newuidmap /usr/bin/newgidmap`（預期有 setuid 位 `-rwsr-xr-x` 或 `getcap` 看到 `cap_setuid`；**預期，未實測**）。

**B. 帳號 `aos-run` 這條**——內容來自 `$AOS_HOME/py/aos/apps/sandbox/root/setup.sh`（實測它的乾跑輸出）。這台沒有它預設的 s6 試驗場，`--s6-bin /usr/bin` 是**推的**（假設 Ubuntu 的 `s6` 套件把程式放 `/usr/bin`，裝完先 `ls /usr/bin/s6-setuidgid` 確認）：
```sh
sudo apt install s6
sh $AOS_HOME/py/aos/apps/sandbox/root/setup.sh --s6-bin /usr/bin          # 乾跑，先看要做什麼
sudo sh $AOS_HOME/py/aos/apps/sandbox/root/setup.sh --s6-bin /usr/bin --apply
```
它做四件：抄 s6 四支到 `/usr/local/bin`、`useradd --system … aos-run`、建 `/srv/aos-run`（2770）、寫 `/etc/sudoers.d/aos-run`（`<你> ALL=(root) NOPASSWD: /usr/local/bin/s6-setuidgid aos-run *`）。

## 裝好之後預期的操作（預期，未實測）

（A 裝好就能做；從程式推。）
```sh
aos-asuser sub:5 -- id
```
預期：`uid=5(games) gid=5(tty) groups=5(tty)`——namespace 裡用 `/etc/passwd` 查名字，5 號剛好叫 games，**不是真的變成 games**。

```sh
aos-asuser sub:5 -- sh -c 'mkdir -m 700 /tmp/as5 && echo hi > /tmp/as5/f'
ls -ln /tmp/as5
```
預期：擁有者是 `100004 100004`，你自己 `cat /tmp/as5/f` → `Permission denied`。

**驗證真的換了身分（預期，未實測）**
- 程式在跑時從外面看：`aos-asuser sub:5 -- sleep 20 &` 再 `ps -o uid,cmd -C sleep` → uid `100004`。
- 讀不到你的家：`aos-asuser sub:5 -- cat ~/.bashrc` → `Permission denied`（`~` 由你的殼展開；家目錄 750）。
- 兩個 subuid 互不相讀：`aos-asuser sub:6 -- cat /tmp/as5/f` → `Permission denied`。
- 救回檔案：`aos-asuser --fix --recursive /tmp/as5` 後 `ls -ln /tmp/as5` → 變成 `1000 1000`，你讀得到。
- B 那條：`sudo -n /usr/local/bin/s6-setuidgid aos-run id` → `uid=…(aos-run)`；`… cat ~/.bashrc` → `Permission denied`（setup.sh 寫的自我檢查）。

## 發現的問題／缺的東西（不修程式）

1. **`--dry-run` 也要 newuidmap 在 PATH**：沒裝 uidmap 就看不到對照表；但 README 說 dry-run「不 fork、不開 namespace」，看不出它也先查工具。
2. **家目錄 750，subuid 走不進 `~`**：`~/aos-home/bin`、工作區、`claude` 都在家目錄底下。沙箱 `user: sub:N` 真跑 agent 時，bwrap 以 100004 的身分綁 `~` 底下的路徑，**推測**會失敗（沒實測）。要嘛工作區與程式放 `/srv` 之類，要嘛給 `~` 加一條 ACL x（見 [11](11-aos-share.md)）。README 只寫了一句「每層祖先也要走得到」。
3. **setup.sh 在 Ubuntu 不合用**：預設 `--s6-bin` 是 `~/code/try/sandbox/s6-root/bin`（這台沒有）；註解叫人用 AUR（Arch 的）；`useradd --shell /usr/bin/nologin`，Ubuntu 的 nologin 在 `/usr/sbin/nologin`。
4. **`sub:5` 在裡面會顯示成 games／tty**，容易誤會成換到系統帳號。
5. **文件沒收錄**：`knowledge/aos/` 沒有 asuser 條目（只有 sandbox.json 提一句）；README 頂上連去的 `py/docs/05-commands.md` 裡找不到 asuser 與 share。
6. 沙箱 `user: "aos-run"` 連 dry-run 都報 `UserBad`（文件有寫，照預期，但想先看 argv 的人看不到）。
