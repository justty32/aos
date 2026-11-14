# B6：aos-sandbox 不是 root 時，`user` 帳號自動接 sudo 身分層（11-14 ok-limits 設計）

← [紀錄 kernel-limits-1114](../kernel-limits-1114.md)｜依據：使用者 11-14 經頂層：「沙箱這塊可以走這條」——(a) 准做。條件：不是 root 又指定 user:aos-run 時，自動在前面接 `sudo -n /usr/local/bin/s6-setuidgid aos-run`；規則不符要清楚報錯，不能默默退回。

## 0. 範圍（只准動這些檔，全在 `proto8/cmd/aos-sandbox/` 底下）

- `bin/aos-sandbox`
- `tests/test_sandbox.py`
- `README.md`（`user` 那一列、「要 root 的那半」）
- `proto8/knowledge/aos/cli/sandbox.json`（repo 源頭，一句一鍵）

## 1. 事實（ok-limits 11-14 在家機實測過）

- sudoers 只有一條 NOPASSWD：`/usr/local/bin/s6-setuidgid aos-run *`。lorkhan 另外還有一條要密碼的 `(ALL) ALL`。
- **`sudo -n -l CMD` 不能拿來預檢**：查 `s6-setuidgid root …` 也回 0，因為有 `(ALL) ALL` 那條，它只看准不准、不看要不要密碼。
- 真的跑一次就看得出來：`sudo -n /usr/local/bin/s6-setuidgid aos-run /usr/bin/true` 退 0；換成 `root`、`951:951`、不存在的帳號，都是 stderr 印 `sudo: a password is required`、退 1。
- sudo 會把 PATH 重設成 secure_path（`/usr/local/sbin:/usr/local/bin:/usr/bin`），而且清掉環境。這條鏈上每一支都已經是絕對路徑；沙箱裡的環境本來就由 bwrap 的 `--clearenv --setenv` 從 argv 帶進去，所以不受影響。
- s6-softlimit 放在 sudo 前面或後面，上限都會生效（實測 `ulimit -t` 都是 5）。

## 2. 設計

### 2.1 什麼時候接

`user` 是帳號字串，不是 `sub:N`，而且**不是乾跑、`os.geteuid() != 0`**。這時原本的 `die("UserBad", "... needs root ...")` 改成走 sudo 鏈。

- root 跑的時候完全照舊：`[s6-softlimit …] s6-setuidgid USER bwrap …`。
- 乾跑：`os.geteuid() != 0` 就印 sudo 鏈，但**不預檢**（乾跑照舊不查環境）。root 乾跑照舊印 s6-setuidgid 鏈。
- 不限只有 `aos-run`：任何帳號字串都走這條，准不准由 sudoers 決定（setup.sh 有 `--runner`，可以換帳號名）。`uid:gid` 這種寫法也一樣走，sudoers 不准就會在 2.3 報錯。

### 2.2 鏈的樣子

```
sudo -n /usr/local/bin/s6-setuidgid USER [s6-softlimit LIMITS…] bwrap … -- prog args…
```

- `sudo`：用 `which("sudo", dry)` 找。PATH 上沒有＝`CommandMissing`。
- s6-setuidgid **寫死** `/usr/local/bin/s6-setuidgid`，不照 PATH 找，因為 sudoers 規則綁的是這個路徑。新增常數 `SUDO_SETUIDGID = "/usr/local/bin/s6-setuidgid"`。非乾跑時檔案不存在或不可執行＝`CommandMissing`，訊息寫 `/usr/local/bin/s6-setuidgid not found (install it with root/setup.sh)`。
- 非 root 這條路**不需要** PATH 上有 `s6-applyuidgid`：root 那邊的 `s6-setuidgid` 會自己去找。所以 `which("s6-applyuidgid")` 只在 root 那條路查。
- 順序：sudo 這段放**最前面**，s6-softlimit 接在它後面。理由是 sudoers 可以用 `Defaults rlimit_*` 改掉上限，放在 sudo 後面設的上限才是最後生效的。
  - 實作：先照原樣組出 `chain`（softlimit 段），最後 `chain = [sudo, "-n", SUDO_SETUIDGID, user] + chain`。
- `sub:N` 照舊接 aos-asuser，不受這條影響。

### 2.3 預檢（規則不符要清楚報錯，不能默默退回）

非乾跑、組好鏈、exec 之前跑一次：

```
subprocess.run([sudo, "-n", SUDO_SETUIDGID, user, "/usr/bin/true"], stdin=DEVNULL, stdout=DEVNULL, stderr=PIPE, timeout=10)
```

- 退 0：照常 exec 整條鏈。
- 非 0 或逾時：`die("UserBad", "not root and sudo does not let me run /usr/local/bin/s6-setuidgid %s without a password (%s); add the sudoers rule with root/setup.sh, or run as root" % (user, sudo 的 stderr 第一行去掉空白；逾時就寫 "sudo timed out"))`，然後退 1。
  - **不退回**成「不換身分照跑」。
  - 這是環境做不到，**不算**設定寫壞，不走「設定壞了＝當沒寫」那條路。
- `/usr/bin/true` 不在的話，改用 `shutil.which("true")`。兩個都沒有就跳過預檢，直接 exec（鏈本身失敗時，sudo 自己會印錯）。

### 2.4 錯誤與說明

- `--help` 的英文說明：`user` 那句補上 "not root: an account name goes through `sudo -n /usr/local/bin/s6-setuidgid USER` (the sudoers rule from root/setup.sh); refused = UserBad"。
- 檔頭中文註解第 10 行跟著改。
- 錯誤代號不增加，照舊是 UserBad 和 CommandMissing。

## 3. 測試（tests/test_sandbox.py 加）

1. **乾跑、非 root、`{"user": "aos-run"}`**：argv 前 4 個是 `[<sudo 路徑>, "-n", "/usr/local/bin/s6-setuidgid", "aos-run"]`，第 5 個是 bwrap。
   - 加 `cpu_s: 3`：第 5 個是 s6-softlimit。
   - 用假的 `sudo` 放在 PATH 最前面，讓路徑固定。
   - 測試自己以 root 跑的話，這例 skip。
2. **假 sudo、非乾跑**，在測試暫存夾寫一支 `sudo` 腳本：
   - (a) 第 5 個參數是 `/usr/bin/true`（預檢那次）就 `echo "sudo: a password is required" >&2; exit 1` → aos-sandbox 退 1，stderr 剛好一行 `aos-sandbox: error: UserBad not root and sudo does not let me run /usr/local/bin/s6-setuidgid aos-run without a password (sudo: a password is required); …`，而且 prog 沒有跑（prog 寫一個標記檔，測它不在）。
   - (b) 預檢退 0、真正那次 `shift 3; exec "$@"`（跳過 `-n s6-setuidgid USER`）→ prog 有跑。注意 bwrap 要能用；家機上不能用就 skip。
   - SUDO_SETUIDGID 不存在的機器（`os.path.exists` 為假），非乾跑的例子 skip（CommandMissing 已經在 3. 測）。
3. **CommandMissing**：PATH 上沒有 sudo（PATH 只放一個暫存夾，裡面有 python3、bwrap 的連結，或照既有測試的寫法）→ `CommandMissing`。寫不出來就只測 SUDO_SETUIDGID 不在的那支：把它做成可注入的模組變數也可以。不行的話在回報裡說明，不要另外加旗標。
4. **真的 sudo（家機）**：`sudo -n /usr/local/bin/s6-setuidgid aos-run /usr/bin/true` 退 0 才跑，否則 skip。
   - `aos-sandbox cfg.json id -un`，cfg 只寫 `{"user": "aos-run"}`（`id` 在 /usr/bin，不必另外綁）→ stdout 是 `aos-run`。
   - 再一例 `{"user": "root"}` → 退 1、UserBad。
   - 測試**不寫** /srv/aos-run，也不碰 sudoers。
5. **root 那條路不變**：既有測試全綠。

跑法：`cd ~/code/limits-1114/work && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s proto8/cmd/aos-sandbox/tests -p "test_*.py"`，現在是 15 項。

## 4. 說明文件

- README `user` 那一列：「`帳號`：root 跑＝s6-setuidgid；不是 root＝前面自動接 `sudo -n /usr/local/bin/s6-setuidgid 帳號`（要有 root/setup.sh 那條 sudoers）；sudo 不准＝UserBad，不會不換身分就跑」。
- 「要 root 的那半」11-14 那段：把「我不是 root 時改成前面接 …，後面接 --dry-run 印出的那條」改成「不是 root 時 aos-sandbox 自己接」。setgid 那段跟群組那句保留。
- 提醒：非 root 這條路上，prog、`commands`、`ro`、`rw` 都要是 aos-run 走得到的路徑。`/home/<我>` 是 700 的話，aos-run 進不去。
- knowledge `aos/cli/sandbox.json`：`user` 的說明同步。

## 5. 不做

- daemon 的 `limits.user` 走 sudo（段 5、K 題，不在範圍）。
- 改 sudoers、setup.sh 的行為。
- 自動把路徑 ACL 給 aos-run（要的話叫的那一方自己用 aos-share）。

## 6. Argon 審後的修正（11-14 ok-limits；跟上面衝突時以這節為準）

原文在 `/tmp/ok-limits-argon4/argon.out`（暫存）。9 條全採，第 7 條只寫進文件。

### 6.1 sudo 一律帶 `-k`，而且不准換成 uid 0（Argon 1，高）

lorkhan 有一條要密碼的 `(ALL) ALL`。如果剛好有快取的 sudo 憑證，`sudo -n … s6-setuidgid root` 就會過，等於提權。

- 鏈和預檢**都**改成 `sudo -n -k /usr/local/bin/s6-setuidgid USER …`。
  - `man sudo`：`-k` 跟指令一起用時，忽略快取的憑證，也不會更新快取。
  - 所以只剩 NOPASSWD 規則放得行。ok-limits 實測過，帶 `-k` 時 aos-run 照樣退 0。
  - 2.2、2.3、3. 裡所有的 `["-n"]` 都改成 `["-n", "-k"]`。假 sudo 裡的參數位置因此全部往後挪一格，見 6.4。
- 第二道防線：走 sudo 這條路時，用 `pwd.getpwnam(user)` 查帳號。
  - 查不到：`UserBad unknown account USER`。
  - `pw_uid == 0` 或 `pw_gid == 0`：`UserBad refusing to switch to USER through sudo (uid or gid 0)`。
  - 這條路**只收帳號名**。寫成 `uid:gid` 的，非 root 時報 `UserBad uid:gid needs root; give an account name to go through sudo`，因為 sudoers 規則綁的是帳號名。
  - 這些檢查在乾跑時一樣做，因為只讀 passwd、不碰環境。

### 6.2 user 的格式（Argon 2，高）

- 非 `sub:` 的 `user` 只收兩種寫法：
  - 帳號名 `^[a-z_][a-z0-9_-]*[$]?$`，長度不超過 32；
  - `^[0-9]+:[0-9]+$`。
- 其他寫法（`-` 開頭、空白、換行、大寫等）＝ CfgBad `user must be an account name, uid:gid or sub:N`。
  - 照「設定壞了＝當沒寫」的既有契約：印 warning、不關沙箱照跑。這是使用者 11-12 選的甲，不改。
  - root 跑的那條路也套用這個格式檢查。
- 這樣 `--`、`-x` 都進不了 s6-setuidgid 的 argv，錯誤訊息也不會被換行拆成兩行。

### 6.3 預檢的實作（Argon 3、5，高／中）

- **true 怎麼找**：只從 `("/usr/bin/true", "/bin/true")` 找第一個 `os.path.isfile and os.access(X_OK)` 的。**不用** `shutil.which`，因為呼叫者的 PATH 可能有不可信的目錄，預檢又是在沙箱外跑的。兩個都沒有＝`CommandMissing true not found in /usr/bin or /bin`。2.3 的「跳過預檢」作廢。
- **呼叫**：`subprocess.run([...], stdin=DEVNULL, stdout=DEVNULL, stderr=PIPE, text=True, errors="replace", timeout=10)`，用 try 包起來：
  - `TimeoutExpired` → reason 寫 `sudo timed out`；
  - `OSError as e` → reason 寫 `cannot run sudo: <e.strerror>`。
- **reason 怎麼取**：
  ```python
  lines = [ln.strip() for ln in (r.stderr or "").splitlines() if ln.strip()]
  reason = lines[0] if lines else "exit %d" % r.returncode
  ```
- **訊息改成中性的**，不要猜原因：
  `UserBad sudo -n -k /usr/local/bin/s6-setuidgid USER refused or failed (REASON); this needs the NOPASSWD sudoers rule and the account from root/setup.sh, or run as root`
  - REASON 是 sudo 或 s6-setuidgid 自己的那一行，例 `sudo: a password is required`、`s6-setuidgid: fatal: unable to exec s6-applyuidgid: …`，所以已經看得出是哪邊出錯。
  - 帳號不存在的情況已經在 6.1 先擋掉了。

### 6.4 檢查順序（Argon 6，中）

- `build()` 在 user 那段只做**格式檢查**（6.2）和 6.1 的 passwd 檢查，並記下 `via_sudo = True`。
- 找 `sudo`、檢查 `SUDO_SETUIDGID` 是否存在（`os.path.isfile and os.access(X_OK)`）、在前面接 sudo 那段，**都放到 build() 最後**，也就是所有 CfgBad、PathMissing 檢查之後。
- 預檢放在 exec 之前（不是乾跑才做）。

### 6.5 測試（Argon 4、8，高／中）

- **假 sudo 的參數位置**（帶 `-k` 以後）：`$1=-n $2=-k $3=/usr/local/bin/s6-setuidgid $4=USER $5=prog…`。
  - 預檢那次是 `$5` 為 `/usr/bin/true` 或 `/bin/true`；
  - 真正那次用 `shift 4; exec "$@"`。
  - 第 3 節的「第 5 個」「shift 3」作廢，以這裡為準。
- **euid 可以注入**：模組層級寫 `def euid(): return os.geteuid()`，build 跟預檢都呼叫它。**不加**只給測試用的環境變數來改 euid，免得變成繞過的後門。做法如下：
  - root 與非 root 兩條路的乾跑，用 `importlib.machinery.SourceFileLoader` 載入 `bin/aos-sandbox`，patch `euid`、`SUDO_SETUIDGID`、`pwd.getpwnam`，直接呼叫 build（或主流程裡組 argv 的那個函式；如果沒有拆開，就拆一個出來，例如 `def chain_of(cfg, prog, dry)`，不改行為）。
  - 非乾跑的例子照舊用 subprocess 跑 CLI，搭配假 sudo。
- **skip 條件**：3.2、3.3、3.4 都加 `if os.geteuid() == 0: skipTest`。3.2 的 skip 改成 `not (os.path.isfile(SUDO_SETUIDGID) and os.access(SUDO_SETUIDGID, os.X_OK))`，跟 6.4 一致。
- 既有 15 項裡**沒有**非 root、非 sub 的 `user` 乾跑（ok-limits 查過：只有 `sub:N` 和型別錯的例子），所以 2.1 的改動不會讓既有測試變紅。真的有變紅的話，回報 BLOCKED。
- 3.4 的拒絕例子：真的跑 `{"user": "root"}`（6.1 會在 passwd 檢查就擋下，不會跑到 sudo）和 `{"user": "nobody"}`（真的去問 sudo，因為 `-k` 不吃快取，會得到 `a password is required`），兩個都要 UserBad。
- 再加：`{"user": "--"}`、`{"user": "a\nb"}` 乾跑 → 一行 warning，`config ignored`；`{"user": "951:951"}` 非 root 乾跑 → UserBad。
- 假 sudo、假 prog 放在測試暫存夾裡。aos-run 進不去 0700 的暫存夾，所以**假 sudo 的例子不會真的換身分**；真的換身分只有 3.4 那個 `id -un` 一例。

### 6.6 文件（Argon 7、9，中／低）

README 跟 knowledge 加上：

- 非 root 走 sudo 時，`bwrap`、`s6-softlimit`、prog 本身都要放在 aos-run 讀得到、跑得動的地方（系統路徑，或 `/srv/aos-run` 底下）；`~/.local/bin` 這類 700 家目錄底下的不行。
- **env 白名單的值會出現在 sudo 的指令列紀錄裡**（sudo 預設會記整條指令，bwrap 的 `--setenv KEY VALUE` 也在裡面），所以機密不要列進 `env`。

## 7. 施工中更正（11-14 ok-limits，sol-1 回報 BLOCKED 後）

- 3.4（真的換身分）那一例：aos-sandbox 會自動把設定檔所在的資料夾唯讀綁進沙箱，bwrap 是以 aos-run 的身分去找這個來源路徑的。測試暫存夾在 `/home/lorkhan/…` 底下，`/home/lorkhan` 是 0700，aos-run 走不到，所以報 `Can't find source path … Permission denied`。
- 改法：**只有這一例**，設定夾改用 `tempfile.mkdtemp(dir="/tmp", prefix="aos-sandbox-sudo-")`，建好後 `os.chmod(d, 0o755)`，設定檔 `0o644`（內容只有 `{"user": …}`，沒有機密）；`addCleanup(shutil.rmtree, d)` 收掉，那是測試自己建的暫存夾。
  - bwrap 會先在沙箱內掛一個 tmpfs 到 `/tmp`，再把 `/tmp/aos-sandbox-sudo-…` 綁進去，照順序處理，不會互相衝突。
  - `id` 在 `/usr/bin`，不用另外綁。
- 其他例子照舊放在 TMPDIR。不改家目錄權限，不加 ACL，不寫 `/srv/aos-run`。
- README 第 4 節那條「aos-run 要走得到」的提醒，要寫明**設定檔所在的資料夾**也算在內。
