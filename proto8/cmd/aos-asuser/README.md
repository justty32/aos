# aos-asuser：免 root 換成 subuid 執行程式或救援檔案

← [cmd](../README.md)｜出處：[kernel-limits-plan 03](../../thinking/2026-11/13/kernel-limits-plan/03-opus細化.md)

```sh
aos-asuser [--group sub:G] [--env-all] [--git-safe DIR] [--dry-run] sub:N -- PROG [ARGS...]
aos-asuser --fix [--recursive] [--dry-run] PATH...
aos-asuser sub:5 -- id -u
aos-asuser --help
```

1. `sub:N` 的 N 是 1～60000；`--group sub:G` 的 G 是 1～65536，沒寫就用 N。不能有前導零、正負號或空白。
2. 讀目前使用者的 `/etc/subuid`、`/etc/subgid`：名字或數字 uid 都認，略過空行與註解，同一使用者取第一行；真號＝起點＋N（或 G）－1，不可超過該段個數。
3. 子行程開 user namespace，父行程在外面用 `newuidmap`、`newgidmap` 寫對照表，不用 root。
4. 對照表完成後，子行程清附屬群組、換主群組與 uid，再執行 `--` 後面的程式；清群組失敗不會略過。
5. 父行程轉送 INT／TERM／HUP／QUIT，回傳程式的退出碼；被訊號 S 結束就退 `128+S`，exec 失敗退 127。
6. `--dry-run` 不 fork、不開 namespace，只印兩行對照表（PID 是字面文字）與一行 `exec N:G PROG ARGS...`。

`--fix PATH...` 把整段 subuid／subgid 對進 namespace，以裡面的 0 將指定路徑改回使用者擁有，補上擁有者讀寫權限（夾另補 x）。`--recursive` 先修根，再由上往下修內容，不跟符號連結；符號連結只改擁有者、不改指向目標的權限。某個路徑修不了會印警告、繼續處理，最後退 1。路徑不存在在開 namespace 前報錯；權限不足先放行，進去再試。救援的 dry-run 只印兩行對照表與每個指定路徑的 `fix PATH`，不展開遞迴。

預設環境只帶外面有設的 `PATH`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TZ`、`TERM`、`PYTHONDONTWRITEBYTECODE`、`PYTHONIOENCODING` 與全部 `AOS_*`；`HOME` 設為 `/nonexistent`，API key 等其他變數不帶。`--env-all` 則整份照帶，給後續 bwrap 自己再清。

`--git-safe DIR` 不論是否 `--env-all`，都加上 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=DIR 的絕對路徑`。

`AOS_ASUSER_SUBUID`、`AOS_ASUSER_SUBGID` 可指定替代 subid 檔，只給測試用；真跑 newuidmap／newgidmap 仍只認系統授權的範圍。

aos-sandbox 只換主群組（G＝N）；`limits.groups` 的多群組由 daemon 段 3（C++）處理，這支今天只收一個 `--group`。aos-sandbox 的接線屬另一次施工，本次只新增指令。

沙箱（user ns）裡跑不了，要在 ns 外面跑。工作路徑的每層祖先也要讓換身分後的 uid／gid 走得到。

錯誤代號：`ArgumentsBad`、`FlagUnknown`、`SubidMissing`、`CommandMissing`、`PathMissing`、`NsFailed`；stderr 一行 `aos-asuser: error: CODE reason`，退 1。

測試：`python3 -m unittest discover -s proto8/cmd/aos-asuser/tests`；真跑例子先試 `aos-asuser sub:1 -- true`，不支援就 skip，需在 ns 外重跑。一般測試暫存夾可用 `KERNEL_TEST_TMP` 指定父夾；跨 uid 例子依圖紙用 `/tmp`。

新指令要跑一次 `proto8/install.sh` 才會出現在 `~/.local/bin`。
