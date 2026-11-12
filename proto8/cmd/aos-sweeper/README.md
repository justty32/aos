# aos-sweeper — 清道夫：一台 daemon 的 stderr 封存、封存保留期、收表外子 loop

← [cmd](../README.md)｜本體 [py/aos_sweep.py](../../py/README.md)（`aos-daemon-ctl sweep` 跑同一套）｜設計 [thinking 11-10 sweeper](../../thinking/2026-11/10/sweeper/README.md)

`bin/aos-sweeper`（Python）跑**一輪**就結束；要它每 10 分鐘跑，就在 daemon 表上掛一列 loop 型的 `_sweeper`，節奏交給 aos-loop（跟 `_clock`／`aos-clock` 同一個樣子，daemon 程式完全不認它）。

## 怎麼掛

daemon.json 的 `procs` 加一列（範本 daemon 預設都帶，不要就刪掉這列）：

```json
"_sweeper": {"exec": {"argv": ["aos-sweeper", "--retention-days", "7", "--report", {"$env": "AOS_STACK", "$path": "sweeper_report.json"}]},
             "interval_ms": 600000, "auto_restart": true, "stuck_after_ms": 600000}
```

- 不用給 `--daemon`：daemon 給子項的環境本來就有 `AOS_DAEMON`。`aos-sweeper` 靠 PATH 找（install.sh 放好），列上沒有任何機器位置，搬家、經 git 換機照用。
- `interval_ms: 600000`＝牆鐘 10 分鐘；`pause _clock` 停時間時清道夫照跑（磁碟照樣在長）。改頻率改這個數。daemon 起來第一圈立刻跑一輪。
- `stuck_after_ms: 600000`：一輪可能要壓縮幾百 MB（實測 293 MB 約 2.5 秒）或等殭屍 10 秒，用預設會在中途被標 stuck。不加 `restart_on_stuck`。
- **每台 daemon 自己掛、只管自己**（使用者 11-10）：清道夫只碰它那台表上的列與那台的預設小格 `D/procs/*/`，**不往子 daemon 底下走**。子 daemon 那一列本身的 stderr（它在父表上是一列）歸父的清道夫；子 daemon 自己表上的零件歸子 daemon 自己的清道夫。**沒掛清道夫的 daemon 就沒人清**。
- 停自動清：`aos-daemon-ctl pause _sweeper`（或 stop）；人下的 `aos-daemon-ctl sweep` 照跑。

## 一輪做什麼

1. **封存**：表上每列 stack 裡的 stderr 檔（名字照 `procs_state.json` 頂層的 `procs_stderr`，預設 `stderr.txt`）≥ `--min-bytes`（預設 1 MiB）就 gzip 複製到同一個 stack 的 `stderr_archives/<UTC 毫秒>.txt.gz`，再把原檔**截成 0**（copytruncate；不能改名——零件的 fd 還指著舊檔）。零件用 O_APPEND 寫，截了從 0 接著寫；**一律截到 0、不留尾巴**（截在一行中間的話新行會黏在半截後面）。狂寫時最後一瞬間寫進來的幾行可能掉（實測每秒約 400 行、連封 9 次 0 行遺失）。
   - `procs_stderr` 改成 `err.log`＝封存夾 `err_archives/`、檔名 `….log.gz`（`.gitignore` 要自己加對應一行）。
   - symlink、硬連結（連結數 >1）、不是一般檔＝不碰、一行 warning；絕不截 symlink 指到的檔。
   - stack 是 D 自己的列跳過；兩列同 stack 只封一次。
   - 內容照位元組原樣壓（eca 零件若有終端控制碼也原樣留著）；看的時候 `zcat`／`zless`。
2. **保留期**：檔名時間超過 `--retention-days`（預設 7）的封存檔刪掉；`--retention-days none`＝永不自動刪。範圍＝表上各列＋表外預設小格的封存夾。看**檔名裡的 UTC 時間**、不看 mtime（git checkout、cp 會改 mtime）。只認自己寫的檔名樣式，夾裡別的檔不碰。
3. **行程**（只在 D 的 daemon 活著時；state 窗的 pid＋started_at_ticks＋boot_id 對得上 /proc）：
   - 只收一類：**`D/procs/<名>/` 不在表上**、它自己的 state 窗 pid＋started_at_ticks＋boot_id 對得上本機 /proc、`/proc/<pid>/environ` 的 `AOS_STACK`＝這格且 `AOS_DAEMON`＝這台、活了 60 秒以上＝這台生的、它不認了（表弄丟、手改表）。
   - 第一次看到：往它的 ctl 寫 `{"cmd": "stop", "seq": N}`，記進 `D/.sweeper_pending.json`；它是 aos-loop，跑完這次身體自己收。
   - 之後的某一輪、離寫 stop 已過 `--stop-grace-s`（預設 300 秒）還是同一支：SIGTERM 它的行程群＋底下自成一群的，10 秒後還在就 SIGKILL。
   - 其他只報不碰：真 zombie（daemon 與表上各列底下的）、活著但環境對不上的（例如殼裡手起、stack 剛好放在 `D/procs/` 底下的 aos-loop）、別次開機或**別台機器**寫的窗（boot_id 不同；pid 剛好撞到本機活行程時報一句）、太年輕的。
   - 不碰：表上的列、別台 daemon 的小格、不在 `D/procs/` 底下的、tmux server 與其中的 claude／codex（tmux 自己 daemonize、不是子 loop 的後代；收掉起它的 loop 後 tmux 照活）。daemon 不在（kill -9 後沒人重起）＝一個行程都不碰，活著的子項是等下一台接回的。
   - 小格與檔一律不刪、不改表（下表用 `rm`／`prune`）。
4. **放鎖殘骸**（open-14）：aos-lock 放鎖、收屍改名走、刪到一半留下的 `<鎖>.releasing.<20 位 UTC 奈秒>.<pid>.<ticks>`（/mnt/c 上約每 200～300 次放鎖一個），名字裡的時間超過 10 分鐘（代定）就整夾刪掉。範圍：D 與表上各列、預設小格的 stack 往下 3 層，不進 `procs/`（別的列、子 daemon 的）與封存夾、不跟捷徑；只認這個樣式。報告 `releasing` 欄、stdout `NAME: removed leftover lock folder …`。
5. **報告**：stdout 一事一行（daemon 底下 stdout 是 /dev/null）；給了 `--report FILE` 另寫一份 JSON（暫存再改名）：時間、封存了什麼、刪了什麼、封存總量、`.bad-*` 份數、行程那半做了什麼、warning。

不碰：`*.bad-*` 留證檔（只數份數）、history、observed、ledger、歸檔信、`.trash`。不跟 symlink：捷徑不跟進去、不動它（掃的只有表上各列的 stack 頂層與 `D/procs/*/`，一律 lstat）。只長不消、第一版刻意不碰的其他檔（live.jsonl、history、ledger…）與理由：[設計 § 8](../../thinking/2026-11/10/sweeper/01-設計.md#8-只長不消第一版不碰的之後可加給使用者一眼決定)。

## 旗標

```
aos-sweeper [--daemon D] [--report FILE] [--retention-days N|none] [--min-bytes N] [--stop-grace-s S] [--dry-run]
```

`--daemon` ＞ `$AOS_DAEMON` ＞ `./.stack`。`--retention-days` 收正整數或 `none`；`0` 不收（照字面是「立刻全刪」，那是 `aos-daemon-ctl sweep --purge`）。`--dry-run`＝只印會做什麼，任何檔與行程都不動（鎖檔不在也不建、不寫報告）。

## 同時兩個

同一台同時只有一個清道夫：`D/.sweeper.lock` 的 flock。常駐那隻拿不到＝warning「skipped this round」、退 0；`aos-daemon-ctl sweep` 等最多 `--timeout-s` 秒、等不到 `SweepBusy`。

## 結束碼

0＝這輪做完（有發現、有 warning、拿不到鎖跳過都是 0；表讀不了＝warning、這輪什麼都不做、0）。1＝自己的錯：`ArgumentsBad`、`FlagUnknown`、`DaemonMissing`（D 不是資料夾）、`WriteFailed`（`--report` 寫不了）。**不會退 10**（aos-loop 會當成 done）；退 1 會讓跑它的 loop 整支結束、靠 `auto_restart` 重起，連 3 次快速失敗留 stopped＋reason。

## 檔（全部不進 image）

| 檔 | 在哪 | 誰寫 |
|---|---|---|
| `stderr_archives/*.txt.gz` | 每列 stack | 封存 |
| `sweeper_report.json` | `--report` 指的地方（範本列＝清道夫自己的 stack） | 每輪 |
| `.sweeper.lock` | daemon stack | flock |
| `.sweeper_pending.json` | daemon stack | 寫過 stop 的表外子 loop |

`cmd/aos-agent/stack.gitignore` 擋 `**/stderr_archives/`、`**/sweeper_report.json`、`**/.sweeper.lock`（`.sweeper_pending.json` 被 `**/.*` 擋）；報告裡有 pid 與絕對路徑，更不能進 git。
