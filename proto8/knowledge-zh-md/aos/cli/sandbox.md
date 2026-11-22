# `knowledge/aos/cli/sandbox.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/sandbox.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/sandbox.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Running a program in a sandbox`**

# 在沙箱裡跑程式

用 aos-sandbox 跑一個程式，只給它設定允許的路徑、網路和限制。

**`#/aos-sandbox: run a program in a sandbox`**

# aos-sandbox：在沙箱裡跑程式

```sh
aos-sandbox --dry-run cfg.json cat /work/a.txt     # prints the argv it would exec, one JSON line
aos-sandbox rw.json sh -c 'echo y > /work/b'       # works: /work is in rw
aos-sandbox meta.json#/x/sandbox cat /work/a.txt   # a config inside a bigger file
```

它組出 `[s6-softlimit ...] [s6-setuidgid USER] bwrap ... -- prog args` 然後 exec 它，所以結束碼、stdin 和 stdout 都是 prog 的（訊號 N = 128+N，例如 143）。非零而且有一行 `aos-sandbox: error:` = aos-sandbox 失敗；沒有那行的話，是 prog 自己的代碼。沒列出的路徑看不見；唯讀路徑拒絕寫入（`Read-only file system`）。只有 `rw` 路徑和 `/tmp`（空的，prog 結束就消失）可以寫：寫到其他任何地方，連看不見的路徑也一樣，會以 `Read-only file system` 失敗，而不是悄悄消失。如果找不到 CONFIG 但找得到 `CONFIG.json`，就用那個。`/proc` 和 `/dev` 一定在。旗標可以放在 CONFIG 前面或後面；PROG 和它的參數原樣轉交。壞掉的 CONFIG（不是 JSON、不是物件、某個鍵型別錯，例如 `ro must be an array of non-empty strings`、一個 `$ref`、沒設的 `$env` 變數、讀不了的檔案）當成沒寫：PROG 會在「沒有」沙箱的情況下跑，stderr 會出現一行 `aos-sandbox: warning: sandbox config ignored, running unsandboxed: ...`。錯誤：`CfgMissing`（沒有這個檔案，或指標指到空的）、`PathMissing`（列出的某個路徑不存在）、`CommandMissing`（下面其中一個找不到：bwrap；有設限制時的 s6-softlimit；`user` 要的 s6-setuidgid、aos-asuser、sudo 或 `true`；`commands` 裡的某個名字；不用沙箱跑時的 PROG 本身）、`UserBad`、`EnvBad`（有設 AOS_HOME 但它不是 aos home）。

**`#/Config keys`**

# 設定的鍵

一個 JSON 物件；所有鍵都可省略；不認得的鍵忽略。範例：`{"rw": ["/work"], "commands": ["aos-exec"], "net": false}`。

- `ro`、`rw`：看得見的路徑（唯讀 / 可寫）。兩者巢狀時，較深的路徑勝出：`{"rw": ["/repo"], "ro": ["/repo/.git"]}` = /repo 可寫，/repo/.git 唯讀。放 CONFIG 的資料夾一定看得見（唯讀，除非某個 `rw` 路徑涵蓋它），所以工具的 `_entry` 可以用相對於它資料夾的路徑指名 `inner`；機密不要放在那個資料夾。`base`：唯讀的系統基底（預設 /usr /bin /sbin /lib /lib64 /etc）。`commands`：在 PATH 上找得到的指令名稱；它們的資料夾變成唯讀可見。aos 指令（它真正的檔案在某個 aos home 的 `bin/` 裡，旁邊有 `lib/aos`）則會讓整個 aos home 變成唯讀可見；機密不要放在 home 裡。有設 `$AOS_HOME` 時 home 就是它（它必須有 `install.py` 和 `bin/`，否則 `EnvBad`）；只有 AOS_HOME 沒設時，home 才是指令所來自的那個 home。
- `net`：網路（預設 false：只有沙箱自己的 loopback）。
- `mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`：透過 s6-softlimit 的限制（它必須在 PATH 上）。`cpu_s` 是 CPU 時間，不是實際經過的時間。
- `user`：帳號名稱（最多 32 個字元，符合 ^[a-z_][a-z0-9_-]*[$]?$）、數字的 uid:gid，或 sub:N（1 到 60000，不能有前導零，透過 aos-asuser）。root 照舊用 s6-setuidgid。不是 root：帳號會在 s6-softlimit 之前經過 `sudo -n -k /usr/local/bin/s6-setuidgid USER`；需要 root/setup.sh 設好的 NOPASSWD 規則和帳號。-k 會忽略快取的憑證。在這條路上，不認得的帳號、uid/gid 0 和數字的 uid:gid 都是 UserBad，連 dry-run 也是。其他格式不對的名字算壞掉的設定。exec 之前，會用系統的 true 指令檢查 sudo；被拒或失敗是 UserBad，絕不會退回不用沙箱跑。dry-run 印出整條鏈，不做事先檢查。
- 在 sudo 這條路上，bwrap、s6-softlimit、prog、commands、ro 和 rw 必須是 aos-run 搆得到的（系統路徑或 /srv/aos-run）；在權限 700 的 home 底下的執行檔，例如 ~/.local/bin，不會有用。ACL 不會自動加。
- env 白名單裡的值，會透過 bwrap 的 --setenv KEY VALUE 參數出現在 sudo 的指令列紀錄裡；不要把機密放在 env。
- `env`：要傳進去的變數名稱。預設是 PATH、語系、TZ、PYTHON*、六個 AOS_ 執行變數，以及 AOS_DAEMON、AOS_LLM_KERNEL、AOS_KERNEL、AOS_CLOCK、AOS_HOME；給一個清單會整個取代預設。API 金鑰預設絕不傳。
- 值可以是 `{"$env": NAME, "$path": ..., "$prefix": ...}`。

`aos-agent ctl add --limits` 和 `aos-daemon-ctl add --limits` 只從這張清單收限制的鍵和 `user`（`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`、`user`），外加 `mem_total_mb` 和 `procs_total`；其他任何鍵都是 `ArgumentsBad`（daemon 的 cgroup 限制；aos-sandbox 不用它們）。更多旗標：跑 `aos-sandbox --help`。
