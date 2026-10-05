# 帳號模組：真 root 手動驗收手冊

← [筆記索引](README.md)｜[plan m3m 模組五](../plan/m3m-daemon-modules/06-模組五-帳號.md#模組五帳號modulesaccount)｜正本 [B-646](../spec/daemon/account.md)、[P-126](../spec/protocol/daemon/account.md)｜[WAIT_USER](../../wf/WAIT_USER.md)

> 2026-10-05 依現行程式校正（`proto6/src/py` 最後改動 `41edba47`）：訊息模組改成第二十五批的多扇門寫法（`modules.mq` 門名→路徑、每項 `"mq"` 訂門、`aos-mq send|take <門的 socket>`、信原樣不包 `from`／`msg`）、控制 socket 環境變數改名 `AOS_DAEMON_CTL_SOCKET`、補建黑名單帳號 `aostest9`、先建好鎖檔、重開 daemon 後重抓 `$MAIN`。

原本照 commit `6583f565`（帳號模組併進 main）的程式寫的。自動測試已經用 `unshare --map-auto` 假 root 驗過大部分（`proto6/src/py/tests/test_account_policy.py`、`test_account_ns.py`，原 `test_account.py`），這份只補**只有真 root 才驗得到的**部分，順便把主要行為在真環境再走一遍。

**一定要在可以丟掉的機器上做**（VM、測試機）：會建帳號、刪帳號、用 root 開程序。

全程開兩個終端機：**終端機 A** 跑 daemon（前景，看它的 stdout／stderr），**終端機 B** 打其他指令。下面用 `$ME` 代表你登入的帳號（叫 sudo 的人）。

---

## 1. 準備

需要：root（能 `sudo`）、Python 3.9 以上（`python3 --version`）、cgroup v2 與 systemd（只有第 3.11 節選做要用）。

```sh
# B：把程式放到別的帳號讀得到的地方（家目錄常是 700，別的帳號進不去）
sudo mkdir -p /srv/aos-test/run
sudo cp -r <repo>/proto6/src/py /srv/aos-test/py
sudo chmod -R a+rX /srv/aos-test/py
sudo chmod 777 /srv/aos-test/run          # 任務（別的帳號）和主程式（$ME）都要寫

# 測試帳號：aostest1、aostest2（帶補充群組 aosgrp）、aostest3（之後會被刪）、aostest9（黑名單用，要真的存在）
sudo groupadd aosgrp
sudo useradd -m aostest1
sudo useradd -m -G aosgrp aostest2
sudo useradd -m aostest3
sudo useradd -m aostest9
id aostest2                               # 應該看到 groups=…,aosgrp
```

`<repo>` 換成 aos repo 的路徑。之後所有指令裡的 `$ME` 用 `echo $ME` 確認是你自己（沒有就 `ME=$(id -un)`）。

## 2. 設定檔與 inst

```sh
# B：用 python 產生 inst 與設定檔（指令裡有引號，手寫 JSON 容易寫壞）
cd /srv/aos-test/run
python3 - <<'EOF'
import json
R = "/srv/aos-test/run"
PY = "/srv/aos-test/py/bin"
WHO = 'echo "$(id -un) | $(id -Gn) | $HOME $USER $LOGNAME" > %s/who.%s'
OUT = {"stdout": {"$opt": "inherit"}, "stderr": {"$opt": "inherit"}}   # 任務的輸出交給 daemon 寫進 out.log／err.log
insts = {
    "a.json": WHO % (R, "a") + "; echo hello-from-a",
    # 寄、取的第一個參數是「門」的 socket 路徑：daemon 給每一項 AOS_DAEMON_MQ_<門名>（這裡門名 MAIL）
    "b.json": WHO % (R, "b") + "; python3 %s/aos-ctl status > %s/ctl.b; python3 %s/aos-mq send \"$AOS_DAEMON_MQ_MAIL\" '{\"hi\":1}'" % (PY, R, PY),
    "c.json": WHO % (R, "c") + "; python3 %s/aos-mq take \"$AOS_DAEMON_MQ_MAIL\" >> %s/got.c" % (PY, R),
    "d.json": WHO % (R, "d"),
}
for name, script in insts.items():
    json.dump(dict({"argv": ["sh", "-c", script]}, **OUT), open(name, "w"), indent=2)
json.dump({
    "cwd": R,
    "interval_ms": 3000,
    "exec_out_path": "out.log",
    "exec_err_path": "err.log",
    "modules": {
        "account": {"allow": ["aostest*"], "deny": ["aostest9"]},
        "control": {"socket": "./aos.sock"},
        "mq": {"MAIL": "./mq.sock"},              # 門名 → socket 路徑（相對以 cwd 為準）
        "state": {"$ref": "aos-state.json"},
        "reload": {},
    },
    "insts": {
        "a.json": {},
        "b.json": {"account": {"user": "aostest2"}},
        "c.json": {"account": {"user": "aostest1"}, "mq": ["MAIL"]},   # 訂 MAIL 這扇門才收得到信
        "d.json": {"account": {"user": "aostest3"}},
    },
}, open("daemon.json", "w"), indent=2)
EOF
chmod 644 *.json
touch daemon.json.lock          # 鎖檔先用 $ME 建好：不然第一次 sudo 開時由 root 建（644），3.6 不用 sudo 開會先撞 PermissionError
cat b.json daemon.json          # 看一眼長怎樣
```

| 項 | 用哪個帳號 | 為什麼 |
|---|---|---|
| `a.json` | `$ME` | 沒寫 `account`＝預設帳號；`modules.account.user` 沒寫＝`SUDO_USER` |
| `b.json` | `aostest2` | 白名單 `aostest*` 前綴比到；順便用 `aos-ctl`、寄信給 c |
| `c.json` | `aostest1` | 同上；訂了門 `MAIL`，每次跑取信 |
| `d.json` | `aostest3` | 第 3.8 節會把這個帳號刪掉 |

## 3. 逐項驗收

每一步：**打什麼 → 應該看到什麼 → 不一樣代表什麼**。

2026-10-05 校正時在一般帳號下先跑過的部分（這台沒有 `newuidmap`，`unshare --map-auto` 拿不到，切不了別的帳號）：第 2 節的 python 原樣跑過（路徑、帳號換掉）；拿掉 `modules.account` 的同一份設定實際開起來，3.1 的 stdout 行、3.4 的 socket `srw-rw-rw-`／`AOS_DAEMON_CTL_SOCKET` pause／resume／狀態檔內容（舊名 `AOS_DAEMON_SOCKET` 回 `no_daemon`）、3.5 的 `ctl.b` 與 `got.c`（`{"hi":1}`）、3.7 的 `reload: need restart: modules`＋`reloaded`、3.10 的 SIGTERM 回 0 刪 socket 都對得上；3.6 表格每一列用 `unshare --user --map-root-user`（假 root）開過，stderr 與回 1 跟表一致（`aostest9` 不存在時是 `no such user`，所以第 1 節補建）。**以下只能真 root 驗**：3.1 降權後真的開起來、3.2 別的帳號與補充群組、3.3 Uid／Gid、3.4 的擁有者、3.5 別的帳號連 socket、3.7 的帳號名單重讀、3.8、3.9、3.10 的 root 端退出、3.11。

### 3.1 用真 sudo 開、`SUDO_USER` 當預設帳號

```sh
# A
cd /srv/aos-test/run
sudo python3 /srv/aos-test/py/bin/aos-daemon --config /srv/aos-test/run/daemon.json
```

- 應該：stdout 每 3 秒左右每項一行 `<時間> inst=a.json exit=0 ms=…`（a、b、c、d 都是 `exit=0`；c 會比別人多幾行，因為 b 每寄一封信就叫醒 c 補跑一次）；stderr 什麼都沒有。
- 不一樣：
  - 馬上結束、stderr `aos-daemon: account: 沒有預設帳號…`：sudo 沒帶 `SUDO_USER`（例如你本來就是 root 登入），在 `modules.account` 加 `"user": "<你的帳號>"` 再試。
  - `aos-daemon: account: … 名單不准` 或 `no such user`：第 1 節帳號沒建好。
  - `aos-daemon: lock: another aos-daemon holds …/daemon.json.lock`：上一個 daemon 還沒停乾淨（`pgrep -af aos-daemon` 看一下）。
  - `exit=126`、`127` 或 err.log 有 `Permission denied`：別的帳號讀不到 `/srv/aos-test/py` 或寫不進 `run/`，回去看第 1 節的 chmod。

### 3.2 各項帳號、補充群組、HOME／USER／LOGNAME

```sh
# B
cat /srv/aos-test/run/who.a /srv/aos-test/run/who.b /srv/aos-test/run/who.c
```

- 應該：
  - `who.a`：`$ME | <你的群組們> | <你的家目錄> $ME $ME`
  - `who.b`：`aostest2 | aostest2 aosgrp | /home/aostest2 aostest2 aostest2`
  - `who.c`：`aostest1 | aostest1 | /home/aostest1 aostest1 aostest1`
- 不一樣：b 沒有 `aosgrp`＝補充群組沒照 `initgroups` 設；HOME／USER 是 root 或 `$ME`＝環境沒換成那個帳號的。

### 3.3 主程式降權、root 端還是 root

```sh
# B
MAIN=$(pgrep -u "$ME" -f 'bin/aos-daemon --config'); echo $MAIN
ROOTSIDE=$(pgrep -f 'bin/aos-daemon-root'); echo $ROOTSIDE
grep -E '^(Uid|Gid|Groups)' /proc/$MAIN/status
grep '^Uid' /proc/$ROOTSIDE/status
ps -o user=,pid=,ppid=,args= -p $MAIN,$ROOTSIDE
```

- 之後 daemon 每重開一次（3.6、3.9、3.10、3.11），都要在 B 重打上面第一行重抓 `$MAIN`。
- 應該：主程式的 `Uid:` 四欄全是你的 UID（沒有 0）、`Gid` 是你的、`Groups` 是你的群組；root 端 `Uid:` 四欄全是 `0`、它的 ppid 是主程式。
- 不一樣：主程式 Uid 裡有 0＝沒降權（嚴重）；`pgrep` 找不到主程式但找得到 root 擁有的 python＝降權沒發生；root 端不是 0＝root 端開錯了。

### 3.4 socket 666、輸出檔與狀態檔的擁有者

```sh
# B
ls -l /srv/aos-test/run/aos.sock /srv/aos-test/run/mq.sock /srv/aos-test/run/out.log /srv/aos-test/run/err.log
AOS_DAEMON_CTL_SOCKET=/srv/aos-test/run/aos.sock python3 /srv/aos-test/py/bin/aos-ctl pause a.json
ls -l /srv/aos-test/run/aos-state.json /srv/aos-test/run/daemon.json.lock; cat /srv/aos-test/run/aos-state.json
AOS_DAEMON_CTL_SOCKET=/srv/aos-test/run/aos.sock python3 /srv/aos-test/py/bin/aos-ctl resume a.json
```

- 應該：兩個 socket 是 `srw-rw-rw-`、擁有者 `$ME`；`out.log`（裡面有 `hello-from-a`）擁有者 `$ME`；`err.log` 只在任務有寫 stderr 時才會有，有的話擁有者也是 `$ME`；pause 之後 `aos-state.json` 出現、擁有者 `$ME`、內容是 `{"insts": {"a.json": {"paused": true}}}`（resume 後變回 `{"insts": {}}`）；鎖檔 `daemon.json.lock` 擁有者 `$ME`（第 2 節 `touch` 的；沒 touch 的話會是 root，正常）；A 終端機有 `inst=a.json paused`、`inst=a.json resumed`。
- 不一樣：擁有者是 root＝那個檔是降權前建的或主程式沒降權；`aos-ctl` 回 `no_daemon: 沒有 AOS_DAEMON_CTL_SOCKET…`＝環境變數名打錯（舊名 `AOS_DAEMON_SOCKET` 已不認）。

### 3.5 別的帳號的任務用 aos-ctl、aos-mq

```sh
# B（等 b、c 各跑過兩輪）
cat /srv/aos-test/run/ctl.b
cat /srv/aos-test/run/got.c
```

- 應該：`ctl.b` 是一行 JSON，`{"ok":true,"inst":"b.json","running":true,…}`（它自己正在跑）；`got.c` 有好幾行 `{"hi":1}`（信原樣，不加寄件人之類的欄位）。
- 不一樣：`ctl.b` 空的、err.log 有 `connect: … Permission denied`＝socket 不是 666 或 `run/` 資料夾權限擋住；err.log 有 `connect: : Invalid argument`（路徑是空的）＝任務沒拿到 `AOS_DAEMON_MQ_MAIL`（`modules.mq` 沒掛或門名打錯）；`got.c` 一直是空的、err.log 沒錯誤＝`c.json` 沒訂 `MAIL`（信寄到沒人訂的門會被丟掉）。

### 3.6 名單

每次改完 `daemon.json` 都先在 A 按 Ctrl-C 停掉，再照 3.1 開，看它有沒有開起來。改完記得改回原樣（或先 `cp daemon.json daemon.ok.json` 備份）。

| 改法 | 應該 |
|---|---|
| `c.json` 的帳號改成 `aostest9`（黑名單） | 立刻結束、回 1，stderr `aos-daemon: account: insts 的 "c.json"：帳號 aostest9 名單不准`（看到 `no such user aostest9`＝第 1 節沒建 aostest9） |
| `c.json` 的帳號改成 `root` | 同上，`帳號 root 名單不准` |
| `"allow": ["*"]`、`c.json` 用 `root` | 還是名單不准（root 不管名單一律不准） |
| `"deny": ["aostest9", "<$ME 的前幾個字>*"]`（比到預設帳號） | 回 1，`deny 比得到預設帳號 <$ME>`；`allow` 拿掉再試一次，一樣 |
| `"allow": ["aos*test"]` | 回 1，`modules.account.allow 的 "aos*test"：* 只能寫在結尾` |
| `"user": "root"` 加進 `modules.account` | 回 1，`預設帳號 root 是 root` |
| 不用 sudo 開（`python3 …/aos-daemon --config …`） | 回 1，`掛了 modules.account 要用 root 開`（看到 `PermissionError: … daemon.json.lock`＝鎖檔是 root 建的，`sudo chown $ME daemon.json.lock` 再試） |

用 `echo $?` 看結束碼（sudo 會把 daemon 的碼原樣回給你）。

### 3.7 重讀設定

daemon 照 3.1 開著。

```sh
# B：加一項用名單不准的帳號（daemon 重開過就先重抓 $MAIN）
MAIN=$(pgrep -u "$ME" -f 'bin/aos-daemon --config'); echo $MAIN
cd /srv/aos-test/run && cp daemon.json daemon.ok.json
python3 - <<'EOF'
import json; c = json.load(open("daemon.json"))
c["insts"]["e.json"] = {"account": {"user": "aostest9"}}
json.dump(c, open("daemon.json", "w"), indent=2)
EOF
cp a.json e.json
kill -HUP $MAIN
```

- 應該：A 的 stderr 一行 `aos-daemon: reload: insts 的 "e.json"：帳號 aostest9 名單不准`；stdout 沒有 `inst=e.json added`、沒有 `reloaded`；a～d 照跑。（主程式是 `$ME`，所以 `kill` 不用 sudo。）

```sh
# B：改名單
cp daemon.ok.json daemon.json
python3 - <<'EOF'
import json; c = json.load(open("daemon.json"))
c["modules"]["account"]["allow"] = ["aostest1"]
json.dump(c, open("daemon.json", "w"), indent=2)
EOF
kill -HUP $MAIN
```

- 應該：stdout `reload: need restart: modules`，接著 `reloaded`；b（aostest2，已不在新名單）照樣用 aostest2 跑（名單改了不套用）。
- 不一樣：b 停了或報錯＝名單被套用了。

```sh
# B：改回
cp daemon.ok.json daemon.json && kill -HUP $MAIN
```

- 應該：stdout 只有一行 `reloaded`（`modules` 跟開起來時一樣，不再印 `need restart`）。

### 3.8 開起來之後才刪帳號（A6）

daemon 照 3.1 開著、d 在跑。

```sh
# B
sudo userdel aostest3
```

- 應該：接下來 d 每一輪 stdout 是 `inst=d.json exit=1 ms=…`，stderr 每輪一行 `aos-daemon: account: no such user aostest3`；a、b、c 照跑、daemon 沒退出。
- 不一樣：daemon 整個退出＝錯誤沒被當成那一次的 exit=1；d 還是 `exit=0`＝root 端沒在開跑那一刻重查帳號。
- `userdel` 說 aostest3 正在用（`user aostest3 is currently used by process …`）：剛好碰上 d 在跑，過一秒再打。

收尾：`sudo useradd -m aostest3`（後面還要用就建回來）。

### 3.9 kill 掉 root 端

```sh
# B
sudo kill -9 $(pgrep -f 'bin/aos-daemon-root')
```

- 應該：A 的 daemon 立刻結束，stderr `aos-daemon: account: root 端不見了`；在 A 打 `echo $?` 是 `1`；`aos.sock`、`mq.sock` 被刪掉。
- 不一樣：daemon 還開著＝沒發現 root 端不見了。

### 3.10 正常停

照 3.1 再開一次（B 照 3.3 第一行重抓 `$MAIN`），在 A 按 Ctrl-C（或在 B `kill -TERM $MAIN`）。

- 應該：daemon 結束，`echo $?` 是 `0`；一兩秒內 `pgrep -f 'bin/aos-daemon-root'` 什麼都沒有（root 端讀到主程式那頭關了就自己退出）。
- 不一樣：root 端還在＝它沒在 socketpair 關掉時退出。

### 3.11（選做）跟收屍／cgroup 模組一起用

在 `daemon.json` 的 `modules` 加 `"cgroup": {}`（用編輯器或照 3.7 的 python 寫法），把 `b.json` 改成會留背景程序：

```sh
# B
cd /srv/aos-test/run
python3 -c 'import json; json.dump({"argv": ["sh", "-c", "sleep 1000 & echo $! >> /srv/aos-test/run/bg.b; exit 0"]}, open("b.json", "w"))'
# A
cd /srv/aos-test/run
sudo systemd-run --scope -p Delegate=yes python3 /srv/aos-test/py/bin/aos-daemon --config /srv/aos-test/run/daemon.json
```

- B 照 3.3 第一行重抓 `$MAIN`。
- 應該：開頭每項一行 `inst=… cgroup=i-<16 個 hex>`；b 每一輪 `inst=b.json exit=0` 之後接一行 `inst=b.json reaped`；`ps -o user=,pid= -p $(cat bg.b | tr '\n' ',' | sed 's/,$//')` 什麼都沒有（都被清掉了）；
  `ls -l /sys/fs/cgroup$(dirname $(grep ^0:: /proc/$MAIN/cgroup | cut -c4-))` 裡的 `i-*` 框擁有者是 `$ME`。
- 不一樣：開不起來、stderr 有 traceback 提到 `cgroup`＝那台的 systemd 沒有把 scope 委派好（不是帳號模組的問題，記下來就好）；沒有 `reaped`、`sleep` 還在＝別的帳號的程序沒被放進框。

## 4. 收拾

```sh
# A：Ctrl-C 停 daemon
# B
pgrep -f 'aos-daemon' && sudo pkill -f 'aos-daemon'
sudo pkill -u aostest1; sudo pkill -u aostest2; sudo pkill -u aostest3
sudo userdel -r aostest1; sudo userdel -r aostest2; sudo userdel -r aostest3; sudo userdel -r aostest9
sudo groupdel aosgrp
sudo rm -rf /srv/aos-test
```

## 5. 驗完回報什麼

照節號回我一張表就好：

| 節 | 結果 | 備註 |
|---|---|---|
| 3.1 | 過／不過 | … |

不過的那幾節，貼：

- A 終端機那段的 stdout 與 stderr（從開起來到出事後幾行）。
- 那一節要 `cat`、`ls -l`、`grep` 的輸出。
- 那台的 `uname -r`、`python3 --version`、`sudo -V | head -1`，以及當時的 `daemon.json`。

另外請告訴我：3.11 有沒有做、那台是什麼環境（VM、哪個發行版）。
