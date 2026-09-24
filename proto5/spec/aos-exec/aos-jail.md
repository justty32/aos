← [aos-exec](README.md)｜[spec 總導航](../README.md)｜實作：[lib/aos_jail.py](../../lib/aos_jail.py)＋[cli/aos-jail](../../cli/aos-jail)｜誰用它：[aos-agent access.md](../aos-agent/access.md)

# aos-jail：把一支程式關進 bwrap 跑（09-24 access-impl）

一句話：**照命令列參數組一串 bwrap、清環境，然後把自己換成 bwrap。** 不讀 `access.json`、不解指示詞——那是 aos-agent 送件時的事，它只照參數做。純標準庫。

## 用法

```
aos-jail [--mount NAME=PATH]… [--mount-ro NAME=PATH]… [--chdir NAME] [--net on|off] [--setenv K=V]… -- PROG [ARGS…]
```

| 參數 | 意思 |
|---|---|
| `--mount NAME=PATH` | PATH 可寫掛到 `/work/NAME` |
| `--mount-ro NAME=PATH` | 唯讀掛 |
| `--chdir NAME` | 起點＝`/work/NAME`（要是上面掛的名字）；沒給＝`/work` |
| `--net on\|off` | 預設 `off`（連 localhost 都不通）；`on`＝共用主機網路 |
| `--setenv K=V` | 多給工具一個環境變數（會過濾，下面） |
| `-- PROG [ARGS…]` | 要跑的程式；`--` 必寫 |

- NAME：`[a-z0-9_-]+`，不能重複；PATH 要是絕對路徑。
- PROG 含 `/`：必須是絕對路徑；realpath 後它的資料夾唯讀掛到 `/opt/tool`，執行 `/opt/tool/<檔名>`（同資料夾的模組、設定檔一起看得到）。不含 `/`：照牢裡的 PATH 找。

## 牢裡有什麼

- `--unshare-all`（新的 user／pid／net／ipc／uts／cgroup namespace；`--net on` 再 `--share-net`）、`--die-with-parent`、`--new-session`。
- `/usr` 唯讀；`/bin`、`/lib`、`/lib64`、`/sbin` 照主機：是連結就 `--symlink` 同樣的目標，是資料夾就 `--ro-bind-try`。
- `--proc /proc`（新的，只看得到牢裡的行程）、`--dev /dev`（最小）、`--tmpfs /tmp`（空的）。
- `/etc` **不整份掛**，只 `--ro-bind-try`：`ld.so.cache`、`passwd`、`group`、`nsswitch.conf`、`localtime`、`hosts`；`--net on` 再加 `resolv.conf`、`ssl/`、`ca-certificates/`。
- `/work`（空資料夾）與每個 `/work/<NAME>`；PROG 含 `/` 時的 `/opt/tool`。
- 其他（家目錄、agent 家、kernel 家、金鑰檔）一律看不到——**例外是 `/opt/tool`**：PROG 所在的整個資料夾都看得到，程式放在 agent 家根目錄就等於把整個家唯讀給它（`aos-agent check` 會 warn）。stdin／stdout／stderr 是呼叫者開好的 fd，原樣帶進去。

## 環境

`--clearenv` 之後只 setenv：

- `PATH=/usr/local/bin:/usr/bin:/bin`、`HOME=/tmp`；
- `LANG`、`LC_ALL`、`TZ`、`TERM`：aos-jail 自己的環境有才帶；
- `--setenv` 給的（可以蓋掉 PATH、HOME）；
- `AOS_TOOL_ROOT=/work/<chdir>`（沒 `--chdir`＝`/work`），最後設、蓋不掉。base 工具包靠它找工作根目錄，錯誤訊息印的也是這個牢裡路徑（[tools README](../../tools/README.md)）。

`--setenv` 的名字是 `AOS_*`、或含 `KEY`／`TOKEN`／`SECRET`／`PASSWORD`／`CREDENTIAL`（不分大小寫）、或是 `SSH_AUTH_SOCK`＝**一律丟掉**，stderr 印一行 `aos-jail: 丟掉環境變數 <名>…`（工具的 stderr 寫 `merge` 時這行會進結果）。

## 執行與退出碼

最後 `exec` bwrap：行程就是 bwrap（再來是工具），kernel 逾時砍 process group 砍得到。

| 碼 | 什麼時候 |
|---|---|
| 工具的碼 | 正常跑完：bwrap 傳回工具的退出碼 |
| 1 | bwrap 自己失敗（掛的 PATH 不存在、user namespace 被關了…），stderr 是 bwrap 的訊息 |
| 2 | 用法錯：stderr `aos-jail: 用法錯：<哪裡>` 加一行用法 |
| 126 | 找不到 bwrap：stderr `aos-jail: 找不到 bwrap（bubblewrap）；Arch/Manjaro: sudo pacman -S bubblewrap，Debian/Ubuntu: sudo apt install bubblewrap` |

## 例子

```
$ aos-jail --mount ws=/home/u/amy/workspace --chdir ws -- sh -c 'pwd; cat ../../home/u/amy/info.json'
/work/ws
cat: ../../home/u/amy/info.json: No such file or directory
```

## 限制

`net off` 也擋不住 mount 裡的 Unix socket；硬連結、資源上限、同批互蓋都不管（[agent access.md](../agent/access.md)〈擋不住的〉）。
