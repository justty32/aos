# 圖紙 B3：aos-asuser（免 root 換成 subuid 再 exec）＋ aos-sandbox 認 `sub:N`（線限 11-14，照 kernel-limits-plan 段 3）

← [線限 11-14 紀錄](../kernel-limits-1114.md)｜設計出處：[03 第一節第 4 點](../../13/kernel-limits-plan/03-opus細化.md)、[04 段 3](../../13/kernel-limits-plan/04-施工與驗收.md)、[08 G7、G8、G10](../../13/kernel-limits-plan/08-群組用法.md)、[06 X1～X6、X13、X19、X28](../../13/kernel-limits-plan/06-試驗紀錄.md)

施工隊照這份寫碼，不做設計決定。圖紙沒寫到、或自相矛盾＝BLOCKED。

## 0. 範圍（只准動這些檔）

- 新增 `proto8/cmd/aos-asuser/bin/aos-asuser`（Python 3，可執行）
- 新增 `proto8/cmd/aos-asuser/README.md`
- 新增 `proto8/cmd/aos-asuser/tests/test_asuser.py`
- 改 `proto8/cmd/aos-sandbox/bin/aos-sandbox`（只改 `build` 裡 `user` 那段、檔頭註解的 `user` 那行、HELP 裡提到 user 的句子）
- 改 `proto8/cmd/aos-sandbox/README.md`（只改設定表的 `user` 那列，加一段「`sub:N`」）
- 改 `proto8/cmd/aos-sandbox/tests/test_sandbox.py`（只新增測試方法，不改舊的）

風格照 `proto8/cmd/aos-tree-start/`。輸出英文；註解繁體中文；新檔頭一句話。

## 1. 事實（施工隊需要知道的）

- 使用者帳號 uid 1000、主群組 1001；`/etc/subuid`、`/etc/subgid` 給他 `100000:65536`。不用 root 就能開 user ns（`unshare(CLONE_NEWUSER)`），再由 **ns 外面的行程**跑 setuid 的 `newuidmap <pid> <ns起> <真起> <個數> ...`、`newgidmap` 替它寫對照表。Python 3.12 起有 `os.unshare(os.CLONE_NEWUSER)`。
- `sub:N`（N＝1～60000）＝ns 裡 uid N ＝真 uid `起點 + N - 1`。換到這個 uid 後，它讀不到使用者 600 的檔、殺不到使用者的行程；寫出來的檔真擁有者是那個 subuid。
- **在已經是 user ns 的地方（例如施工隊自己的 bwrap 沙箱）newuidmap 會失敗**——沙箱裡只對得到 uid 1000。所以真換身分的測試要在偵測到做不到時 skip，由隊長在沙箱外跑。

## 2. aos-asuser 用法

```
aos-asuser [--group sub:G] [--env-all] [--git-safe DIR] [--dry-run] sub:N -- PROG [ARGS...]
aos-asuser --fix [--recursive] [--dry-run] PATH...
aos-asuser --help
```

### 2.1 跑模式（`sub:N -- PROG`）

1. 驗參數：N 是 1～60000 的十進位整數（不准前導 0）；G 是 1～65536；`--` 之後至少一個字（PROG）。不給 `--group`＝G＝N。
2. 讀 `/etc/subuid`、`/etc/subgid` 目前使用者那一行（名字或數字 uid 都認；同 B2：環境變數 `AOS_ASUSER_SUBUID`、`AOS_ASUSER_SUBGID` 給了就讀那個檔，只給測試用）。`N > 個數` 或 `G > 個數`＝`SubidMissing`。
3. 找 `newuidmap`、`newgidmap`（`shutil.which`）。沒有＝`CommandMissing newuidmap not found on PATH`。
4. `--dry-run`：不開 ns、不 fork，stdout 印三行後退 0：
   `newuidmap PID 0 <我的 uid> 1 <N> <subuid起+N-1> 1`
   `newgidmap PID 0 <我的 gid> 1 <G> <subgid起+G-1> 1`
   `exec <N>:<G> <PROG ARGS... 用空白接>`
   （字面的 `PID` 三個字母，不換成數字。）
5. 真跑：開兩條管子（`os.pipe()`：子→父「我開好 ns 了」、父→子「對照表寫好了」），`os.fork()`。
   - **子行程**：`os.unshare(os.CLONE_NEWUSER)`（失敗＝印 `aos-asuser: error: NsFailed unshare: <原因>` 到 stderr、`os._exit(1)`）→ 寫一個位元組給父 → 讀父的一個位元組（讀到 `b"1"`＝好；讀到別的或 EOF＝`os._exit(1)`，父已經印過錯）→ `os.setgroups([])` → `os.setresgid(G, G, G)` → `os.setresuid(N, N, N)` → 環境（見下）→ `os.closerange(3, 65536)`（管子也一起關）→ `os.execvp(PROG, [PROG, *ARGS])`；exec 失敗＝stderr `aos-asuser: error: CommandMissing cannot start <PROG>: <原因>`、`os._exit(127)`。換身分那三步任何一步丟 OSError＝stderr `aos-asuser: error: NsFailed <哪一步>: <原因>`、`os._exit(1)`。
   - **父行程**：讀子的一個位元組（EOF＝子先死了：等它、退它的結束碼）→ 跑 `newuidmap <子pid> 0 <我的uid> 1 <N> <真uid> 1`，再 `newgidmap <子pid> 0 <我的gid> 1 <G> <真gid> 1`（`subprocess.run(..., capture_output=True, text=True)`）→ 任一個退非 0＝stderr `aos-asuser: error: NsFailed newuidmap: <它的 stderr 第一行>`（或 newgidmap）、寫 `b"0"` 給子、等子、退 1 → 都成功就寫 `b"1"` 給子。
   - 父接著轉送訊號：`SIGINT`、`SIGTERM`、`SIGHUP`、`SIGQUIT` 收到就 `os.kill(子pid, 同一個訊號)`。`os.waitpid` 等子結束：正常結束＝退它的碼；被訊號 S 殺＝退 `128 + S`。
6. **環境**：沒給 `--env-all`＝只留白名單裡外面有設的：`PATH`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TZ`、`TERM`、`PYTHONDONTWRITEBYTECODE`、`PYTHONIOENCODING`，與名字以 `AOS_` 開頭的全部；其他（含 `HOME`、各種 API key）都不帶。`HOME` 設成 `/nonexistent`。給了 `--env-all`＝整份照帶（給 aos-sandbox 用，bwrap 自己會再清）。
7. `--git-safe DIR`：環境多三個 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=<DIR 的絕對路徑>`（不管有沒有 `--env-all`）。

### 2.2 救援模式（`--fix PATH...`，08 G7）

把 agent 鎖住的檔改回使用者擁有、使用者可讀寫。做法同上的 fork／管子，但：

- 對照表對**整段**：`newuidmap <pid> 0 <我的uid> 1 1 <subuid起> <個數>`、`newgidmap <pid> 0 <我的gid> 1 1 <subgid起> <個數>`。
- 子行程不換 uid（留在 ns 裡的 0＝外面的使用者，有 ns 裡的權限），對每個 PATH（`--recursive` 時連夾裡全部，用 `os.walk(topdown=True)`，不跟符號連結）：`os.lchown(p, 0, 0)`；不是符號連結的再 `os.chmod(p, 目前權限 | (0o700 if 夾 else 0o600))`。某一個失敗＝stderr 一行 `aos-asuser: warning: cannot fix <p>: <原因>`、繼續，最後子行程退 1（全成功退 0）。父行程照子的結束碼退。
- `--dry-run`：stdout 印兩行對照表（`PID` 字面）＋每個要修的路徑一行 `fix <路徑>`（不展開 `--recursive`，只印給的 PATH），退 0。
- PATH 不在＝`PathMissing`（開 ns 之前就檢查）。

### 2.3 錯誤（stderr 一行 `aos-asuser: error: CODE reason`，退 1）

`ArgumentsBad`（參數壞：sub:N 寫壞、少 `--`、少 PROG、`--fix` 混著 `sub:N`）、`FlagUnknown`、`SubidMissing`、`CommandMissing`、`PathMissing`、`NsFailed`（unshare／newuidmap／換身分失敗）。exec 之後的結束碼都是 PROG 的。

## 3. aos-sandbox 認 `user: "sub:N"`

在 `build` 的 `user` 那段：`user` 是字串、而且以 `sub:` 開頭時，**不走 s6、也不要 root**：

```python
        if user.startswith("sub:"):
            chain = [which("aos-asuser", dry), "--env-all", user, "--"] + chain
        else:
            （原本的 root 檢查與 s6-setuidgid 那三行，一字不改）
```

也就是 `aos-asuser` 排在最前面（在 `s6-softlimit` 之前，`procs` 這種上限才是換身分後那個 uid 的），bwrap 在它後面、照舊清環境。`sub:` 後面寫壞（不是 1～60000）＝`CfgBad("user sub:N needs N from 1 to 60000")`（照這支的慣例＝設定壞了當沒寫）。`which` 找不到 aos-asuser＝照 `which` 原本的 `CommandMissing`。

- 檔頭註解 `user` 那行改成：`#   user     字串：帳號名或 uid:gid → s6-setuidgid（要 root）；sub:N → aos-asuser（免 root，換成 subuid）；沒寫＝不換身分`。
- HELP 裡 `user (account or uid:gid, needs root)` 改成 `user (account or uid:gid, needs root; sub:N = a subuid through aos-asuser, no root)`。
- README 設定表 `user` 那列值改成「`帳號`、`uid:gid` 或 `sub:N`」、做什麼改成「`s6-setuidgid` 換身分（只有 root 能用）；`sub:N`＝前面接 `aos-asuser --env-all sub:N --`，免 root 換成 subuid（[aos-asuser](../aos-asuser/README.md)）」。表下加一段三行：`sub:N` 的意思、bwrap 在 user ns 裡照開（[06 X28](../../thinking/2026-11/13/kernel-limits-plan/06-試驗紀錄.md)）、工作區的每層祖先要給「別人」x 才走得到。
- test_sandbox.py 新增兩例（用 `--dry-run`，不真跑）：`{"user": "sub:5"}` 的 argv 第一個是 aos-asuser 的路徑、接著 `--env-all`、`sub:5`、`--`，之後才有 bwrap；`{"user": "sub:0"}` 是「config ignored」那行 warning。PATH 上沒有 aos-asuser 時，測試自己在暫存夾放一支假的可執行檔 `aos-asuser` 並把那夾放到 PATH 前面。

## 4. README（aos-asuser）

格式照 `proto8/cmd/aos-tree-start/README.md`：標題、`← [cmd](../README.md)｜出處：[kernel-limits-plan 03](../../thinking/2026-11/13/kernel-limits-plan/03-opus細化.md)`、用法區塊、2.1 的步驟縮成五到八行白話、`--fix` 一段、環境白名單、`--git-safe` 一句、錯誤代號一行、「沙箱（user ns）裡跑不了，要在 ns 外面跑」一句、測試怎麼跑、「新指令要跑一次 `proto8/install.sh` 才會出現在 `~/.local/bin`」。

## 5. 測試 tests/test_asuser.py

- 偵測做不做得到：`unshare -U --map-auto true`（`subprocess.run`，退 0 才算做得到）；做不到的那幾例 `skipTest("user namespaces with subuids are not available here")`。
- 測試用假 subid 檔：寫 `<使用者名>:100000:65536`，但**真跑的例子用真的 `/etc/subuid`**（不設那兩個環境變數），因為 newuidmap 只認系統的檔。
- 至少要有：
  1. （真跑）`aos-asuser sub:5 -- id -u` stdout 是 `5`；`-- sh -c 'echo $HOME'` 是 `/nonexistent`；設了 `SECRET_KEY=x` 時 `-- sh -c 'echo ${SECRET_KEY:-none}'` 是 `none`，加 `--env-all` 後是 `x`。
  2. （真跑）在 `tempfile.mkdtemp()` 做一個 `chmod 600` 的檔，`sub:5 -- cat <檔>` 退非 0。
  3. （真跑）`sub:5 -- sh -c 'exit 7'` 退 7；`sub:5 -- sh -c 'kill -TERM $$'` 退 143。
  4. （真跑）在 `chmod 777` 的暫存夾（祖先要走得到：用 `tempfile.mkdtemp(dir="/tmp")`，`/tmp` 是 1777）裡 `sub:5 -- sh -c 'echo hi > f; chmod 600 f'`，外面 `os.stat(f).st_uid == 100004`、讀不到；再 `--fix <f>` 退 0，之後 `st_uid == os.getuid()`、讀得到。
  5. （真跑）`--git-safe /x -- sh -c 'echo $GIT_CONFIG_VALUE_0'` 是 `/x`。
  6. `--dry-run sub:5 -- true` 三行跟 2.1 第 4 步的格式逐字相同（用假 subid 檔）。
  7. 錯：`sub:0`、`sub:60001`、少 `--`、`--fix` 加 `sub:5`、`--fix` 的 PATH 不在、假 subid 檔沒有這個使用者——比退出碼 1 與 CODE。
- 跑法（必須全綠，沙箱裡真跑那幾例是 skip）：`python3 -m unittest discover -s proto8/cmd/aos-asuser/tests`、`python3 -m unittest discover -s proto8/cmd/aos-sandbox/tests`
