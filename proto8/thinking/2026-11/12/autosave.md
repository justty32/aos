# 樹在 /tmp 跑、每五分鐘 auto save 到 ~/（11-12 下午公司 WSL 實測）：行得通，但這台 /tmp 跟 ~/ 是同一顆 ext4、不比較快，還每次開機清空——建議整棵放 ~/、auto save 照掛

← [11-12 日索引](README.md)｜試驗場（另一份）：[playground](playground.md)

## 使用者原文

- 第一版：「我接下來打算做一件事，想請你幫我看看可不可行：我會在C:/code/agents/下，弄各種def和ws，然後在WSL啟動daemon和各種proc(並且是/tmp下)，然後定期從/tmp複製各種東西到C:/code/agents/.snapshots。」
- 改方案（實驗做到一半）：「或許可以調整為：仍在/tmp跑(因為這樣快)，然後定期(每五分鐘)複製到~/下的某個地方。ws仍放在WSL，只是定期複製到/mnt/c/...。windows這邊...算了，蛋雕，還是不碰/mnt/c了。快照這塊只是保險，類似遊戲的auto save，有些缺陷沒關係。」
- 接著：「/tmp我以為他是記憶體」

## 結論

- **照新方案做行得通**：樹在 `/tmp` 跑、`~/` 底下每五分鐘存一份；整份 `/tmp` 被刪光後從 `~/` 那份抄回同一路徑再起，樹起得來，fsm 接上舊歷史，eca（haiku）續的是**同一段舊對話**（session id 沒變、記得前面要它記的詞）。
- **「/tmp 比較快」在這台是假的**：`/tmp` 不是 tmpfs，跟家目錄同一顆 `/dev/sdd` ext4（`findmnt -T /tmp` 只找到 `/`）。量下來小檔、改名、json 都在誤差裡；fsm 假腦 10 輪：`~/` 55.1 秒、`/tmp` 53.2 秒、`/dev/shm` 55.3 秒——一輪 5 秒多全花在輪詢與時鐘拍子上，跟碟無關。真正在記憶體的是 `/dev/shm`（tmpfs 7.7G），只有「寫檔＋fsync＋改名」那類快 2～6 倍，對整棵樹沒差。
- **/tmp 會被清**（讀設定推的、沒重開機實測）：這台開了 systemd，`/usr/lib/tmpfiles.d/tmp.conf` 有 `D /tmp 1777 root root 30d`，`systemd-tmpfiles-setup` 開機時帶 `--remove --boot` 跑＝**每次 WSL 開機 `/tmp` 整個清空**；佐證：`/tmp` 最舊的東西就是今天 07:58 開機那一刻建的。另外每天 `systemd-tmpfiles-clean.timer` 會刪 `/tmp` 裡 **30 天沒碰過**的檔——樹在跑也照刪（久沒讀的定義檔、範本會被挑走）。
- **最該改的一點**：既然不快，**整棵（定義、ws、stack）放 `~/`**，就不怕被清、不用還原；auto save 照樣掛，當「讀檔點」（agent 改壞東西時退回五分鐘前）。真要放 `/tmp` 也行，開機後先還原再起樹（指令在下）。
- **`/dev/shm` 不值得**：快不到樹上，WSL 一停就沒、還吃 VM 記憶體（tmpfs 算在 15G 裡），一定得 auto save＋每次開機還原，代價比 `/tmp` 還大。
- aos 程式本身在這種擺法下**沒找到 bug**。

## 怎麼驗的

| 步 | 做什麼 | 結果 |
|---|---|---|
| 1 | 讀設定：`findmnt`、`df`、`stat -f`、`/etc/wsl.conf`、tmpfiles、timer、`loginctl` | `/tmp` 與 `~` 同為 `/dev/sdd` ext4；`/etc/wsl.conf` 只有 `[boot] systemd=true`；`tmp.mount` 不存在；`systemd-tmpfiles-clean.timer` 每天 08:13；沒有 linger、`systemctl --user` 連不上 bus；`cron` active、`crontab` 空 |
| 2 | 三處測速（各 3 回） | 見下表 |
| 3 | 在 `/tmp/aos-run-trial/` 搭一棵：總機（`kernel/llm-kernel` 複本）、根（`daemon-root`）＋`fsm_ann`（假腦 `fake`）＋`eca_bob`（haiku、上限 0.3 美金），`AOS_HOME` 也複製在樹裡（`aos/`） | 都 running；fsm 答 `FAKE ANSWER …`；eca 一輪 6 秒，記下 `PELICAN-7`、用自己的 Write 寫 `note.txt` |
| 4 | 根 `daemon.json` 加 `_autosave`（測試時 20 秒一次） | 每次一份 `~/aos-run-trial-save/<時間>/`，`latest` 指最新；一次 0.16 秒 |
| 5 | 邊跑邊抄：連寄 8 封給 fsm，同時 0.2 秒一次連抄 25 次 | 見「可接受的缺陷」 |
| 6 | 模擬 WSL 沒了：`kill -9` 樹的所有行程、`rm -rf /tmp/aos-run-trial`，再從 `latest` 抄回同路徑、起 | 見「還原」 |
| 7 | 拿邊跑邊抄那批裡**正在處理信**的一份，抄到**別的路徑** `/tmp/aos-run-trial-r2` 起 | 見「還原」 |
| 8 | 畫面：`aos-agent open --detach -t eca_bob`，`tmux capture-pane` 看；另在 `/tmp/aos-trust-probe` 直接開互動 claude | 都沒跳信任提示（原因見坑 7） |

### 測速（ms，三回裡挑中間那回；三回之間差很多，看倍數就好）

| 操作 | `~/` | `/tmp` | `/dev/shm` |
|---|---|---|---|
| 寫 2000 個小 json（shell `>`） | 108 | 107 | 51 |
| 放信：`mkdir tmp/x`＋寫 letter＋`mv` 到 new＋`mv` 到 cur，×2000 | 17738 | 18600 | 16694 |
| history 追加 5000 行 | 63 | 75 | 70 |
| `aos-json set`＋`get` ×40 | 397 | 476 | 191 |
| Python 寫暫存檔＋改名 ×3000（每 100 次 fsync 一次） | 1253 | 984 | 167 |
| **fsm 假腦 10 輪（say＋listen，各一棵新樹）** | **55118** | **53205** | **55298** |

放信那列幾乎全是開 `mkdir`／`mv` 行程的成本；fsync 那列才看得出記憶體快。整棵樹的速度由輪詢間隔（daemon 100～200 ms、時鐘 1 秒一拍）決定，碟快多少都看不出來。

## 推薦的擺法

```
~/aos-run/                ← 整棵（推薦放 ~/；要放 /tmp 就把 T 換成 /tmp/aos-run）
  env.sh                  ← 每個視窗先 source
  aos/                    ← AOS_HOME：proto8 的 lib py templates kernel 複本（放樹裡，存檔時一起帶走）
  defs/root/              ← daemon-root 範本＋autosave.sh＋daemon.json 多一列 _autosave
  defs/llm/               ← kernel/llm-kernel 複本（總機）
  defs/<agent>/           ← 各隻定義
  ws/                     ← 工作區（使用者要留的東西；樹放哪它就放哪）
  stacks/root  stacks/llm ← 兩台 daemon 的 stack
~/aos-run-save/<時間>/     ← auto save，留最新 12 份（五分鐘一份＝一小時），latest 指最新
```

- **ws 放哪**：跟著樹放 `~/`。若樹堅持放 `/tmp`，ws 也照樣在 `/tmp`（auto save 帶著它）；要把 ws 單獨放 `~/` 也可以（`ctl add -w ~/某處`，絕對路徑原樣存），但 claude 的對話資料夾是照 ws 路徑取名的（`~/.claude/projects/-tmp-aos-run-trial-ws/`），之後別再搬 ws。
- **每五分鐘怎麼掛**：比了三種，推薦第一種。

| 掛法 | 這台能不能用 | 好處 | 壞處 |
|---|---|---|---|
| **根 daemon 多一列 `_autosave`（`interval_ms: 300000`，跟 `_sweeper` 同形）** | 能，實測過 | 樹在跑才存、樹停就停；跟樹一起存、一起還原；`aos-daemon-ctl ls` 看得到；壞了留 `stopped`＋原因 | 根停了就不存（本來也不用存） |
| `while sleep 300; do …; done` 另掛一支 proc | 能 | — | 跟上面同一件事、多一支常駐行程，沒有理由選 |
| cron（`*/5 * * * *`） | 能（cron active） | 跟樹無關 | 樹停著也照跑；腳本與環境要另放 `~/`；開機後若先起了一棵新的空樹，它會開始把空樹存成最新 |
| systemd user timer | **不能**：沒有 linger、`systemctl --user` 連不上 bus；開 linger 是改系統設定，沒動 | — | — |

- **要不要留多份**：要。腳本用 `rsync --link-dest` 指上一份，沒變的檔做硬連結、只多存變了的；12 份（20 秒間隔、兩隻 agent）共 16 MB，一份完整 4.4 MB（實際 2.1 MB，`aos/` 佔大半）。

## 照抄

<details><summary>env.sh（放在樹根）</summary>

```sh
# env for an aos tree run from this folder: source it in every window
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT AOS_DAEMON AOS_KERNEL AOS_CLOCK AOS_STACK AOS_WS AOS_AGENT
export T=${T:-$HOME/aos-run}
export AOS_HOME=$T/aos
export AOS_LLM_KERNEL=$T/stacks/llm
export AUTOSAVE_DIR=${AUTOSAVE_DIR:-$HOME/aos-run-save}
```

</details>

<details><summary>defs/root/autosave.sh（實測那份，只改了預設路徑）</summary>

```sh
#!/bin/sh
# autosave.sh - copy the running aos tree ($T) to $AUTOSAVE_DIR/<time>/ (unchanged files hard-linked to the previous save), point latest at it, keep the newest $AUTOSAVE_KEEP
set -eu
SRC=${T:-$HOME/aos-run}
DST=${AUTOSAVE_DIR:-$HOME/aos-run-save}
KEEP=${AUTOSAVE_KEEP:-12}
[ -f "$SRC/stacks/root/procs_state.json" ] || { echo "autosave: error: SourceMissing no tree at $SRC (not saving, old saves kept)" >&2; exit 1; }
mkdir -p "$DST"
now=$(date +%Y%m%d-%H%M%S)
n=1; while [ -e "$DST/$now" ]; do n=$((n+1)); now=$(date +%Y%m%d-%H%M%S)-$n; done
link=
[ -d "$DST/latest" ] && link="--link-dest=$DST/latest"
rc=0
rsync -a --delete --exclude=__pycache__ $link "$SRC/" "$DST/.part-$now/" 2>"$DST/.rsync-stderr.txt" || rc=$?
# 24 = some files vanished while copying (letters moving through the queue, files replaced by rename): fine for an autosave
[ "$rc" = 0 ] || [ "$rc" = 24 ] || { echo "autosave: error: RsyncFailed rsync exited $rc (see $DST/.rsync-stderr.txt)" >&2; exit 1; }
mv "$DST/.part-$now" "$DST/$now"
ln -sfn "$now" "$DST/latest"
ls -1d "$DST"/2* | head -n -"$KEEP" | xargs -r rm -rf
```

rsync 的旗標：`-a`（含權限、時間、symlink 照抄成 symlink——`transcripts/` 那條指向 `~/.claude/...` 的絕對連結抄過去照樣指得到）、`--delete`（存檔裡不留樹上已刪的）、`--link-dest`（輪替省空間）、`--exclude=__pycache__`。鎖檔（`lock`、`.flock`、`*.lock`）都是 0 byte、照抄沒事，不必排除；樹裡沒有 fifo、socket（畫面的 tmux socket 在 `/tmp/aos-tty-<uid>/`，不在樹裡），也沒有怪檔名。

</details>

<details><summary>第一次搭（從 repo 抄；R＝這台 proto8）</summary>

```sh
R=~/repo/aos-tools/proto8; T=~/aos-run
mkdir -p $T/aos $T/defs $T/ws $T/stacks
cp -r $R/lib $R/py $R/templates $R/kernel $T/aos/ && find $T/aos -name __pycache__ -prune -exec rm -rf {} +
cp -r $R/templates/daemon-root $T/defs/root
cp -r $R/kernel/llm-kernel $T/defs/llm
cp -r $R/templates/agent-fsm $T/defs/fsm_ann     # 其他隻照抄
# 上面兩格：env.sh 放 $T/env.sh；autosave.sh 放 $T/defs/root/autosave.sh
cd $T && . ./env.sh
aos-json set 'defs/root/daemon.json#/procs/_autosave' '{"exec": {"argv": ["sh", {"$env": "T", "$path": "/defs/root/autosave.sh"}]}, "interval_ms": 300000, "auto_restart": true, "stuck_after_ms": 120000}'
```

</details>

**起樹**（每個視窗先 `cd ~/aos-run && . ./env.sh`；兩台各自在背景，log 接在樹根）：

```sh
cd ~/aos-run && . ./env.sh
setsid nohup aos-exec --stack stacks/llm defs/llm >> llm.log 2>&1 < /dev/null &
sleep 1
setsid nohup aos-exec --stack stacks/root defs/root >> root.log 2>&1 < /dev/null &
```

（想看 log 就像試驗場那樣開兩個視窗前景跑 `aos-exec --stack stacks/llm defs/llm`、`aos-exec --stack stacks/root defs/root`，Ctrl-C＝那台收工。）

第一次起之後掛 agent：`cd ws && aos-agent -d ../stacks/root ctl add --auto-restart ../defs/fsm_ann`。停：`aos-daemon-ctl -d ~/aos-run/stacks/root shutdown; aos-daemon-ctl -d ~/aos-run/stacks/llm shutdown`（子項睡下，下次起自己醒）。

**auto save**：上面 `_autosave` 那一列就是掛法；手動存一次＝`cd ~/aos-run && . ./env.sh && sh defs/root/autosave.sh`。

**還原**（樹停著或已經被清時；路徑跟存的時候一樣）：

```sh
T=~/aos-run; [ -e $T ] && echo "already there: move it away first" || { mkdir $T && cp -a ~/aos-run-save/latest/. $T/; }
```

然後照「起樹」。要退回更早的一份就把 `latest` 換成 `ls ~/aos-run-save` 裡的時間。一定用 `cp -a` 抄出來再起，**不要直接在存檔資料夾裡起樹**（坑 5）。樹放 `/tmp` 的話：每次 WSL 開機後、起樹前先跑這行（`T=/tmp/aos-run`）。

## 還原實測

- **同路徑、kill -9 後的存檔**（`/tmp/aos-run-trial`）：表上五列都是 `running`、pid 全是死的；起根後五列照起（daemon 比 pid＋`started_at_ticks`，重開機過另比 `boot_id`，見 aos-daemon docs/08），fsm history 18 行→再一輪 22 行接著長；eca_bob 問「剛才要你記的詞」答 `PELICAN-7`，`session.txt` 前後都是 `59843b82-…`（`claude -p --resume` 接上，`.session_home` 的 ws、home、machine 都對得上）。
- **別的路徑、處理信到一半的存檔**（`/tmp/aos-run-trial-r2`；那份 fsm history 7 行、queue/new 有 7 封還沒收、`think/` 有一個在飛的問腦）：起來後 fsm 把在飛那封答完、再把 7 封併成一批答，history 7→18 行，沒有錯誤、沒有重答。表上路徑是相對 stack 存的（`procs/fsm_ann`），整棵換位置照樣對。eca_bob 換了新 session id（`a48b6cf4-…`）——ws 路徑變了，`.session_home` 判「不是這裡的」改開新對話，但 aos-eca-turn 把 history 整理後接在題目前面（reseed），所以它照樣答得出 `PELICAN-7`。**換路徑＝新對話＋帶著摘要，不是續舊的**。

## 可接受的缺陷（邊跑邊抄看到的）

| 現象 | 實際看到 | 為什麼可以接受 |
|---|---|---|
| rsync 退 24「file has vanished」 | 25 次裡 4 次；消失的是正在搬的信（`queue/tmp`、`think/reply/new`、總機 `requests/new` 的 `letter.json`）、`.order.json.*.tmp`、`order.lock/holder.*`、`think/pending.txt`、hook 的 `on_clock.json` | 腳本把 24 當成功；消失的都是一拍內就換掉的東西 |
| 某份存檔缺幾個檔 | 第一份存檔裡 4 個 `on_clock.json` 都不在（每秒用改名換掉，剛好換的那一刻） | 起來後下一拍就重寫 |
| 信卡在半路 | 存檔裡 queue/new 有 1～7 封還沒收、history 停在一輪中間（5、7 行） | 還原起來會照常收信、補完那一輪（上面實測） |
| 兩台 stack 不是同一瞬間 | rsync 依序走，總機與根的 stack 差約百毫秒；存到在飛的問腦 | 實測接得上；最壞是同一題多問一次腦（多花一次錢） |
| 最多丟五分鐘 | 存檔之後到被清之間的事 | auto save 本來就是這樣 |

## 坑（頂層沒問到的也列）

1. **/tmp 的 30 天清理在樹跑著時也會發生**：`systemd-tmpfiles-clean` 每天刪 `/tmp` 裡 atime、mtime、ctime 都超過 30 天的檔；樹放 `/tmp` 跑超過一個月，久沒讀的定義、範本、`aos/` 裡的檔會被挑掉（讀設定推的，沒等 30 天實測）。放 `~/` 就沒這事；要留在 `/tmp` 只能改 tmpfiles 設定（系統設定，沒動）。
2. **AOS_HOME 要跟著樹**：定義用 `{"$env": "AOS_HOME", …}` 指 lib 與範本；AOS_HOME 若指另一個 `/tmp` 底下的 clone，清了就整棵叫不到工具。這次把 `aos/` 放樹裡、一起存一起還原。
3. **開機後還沒還原就起了新樹**：`_autosave` 會把那棵新樹存成 `latest`；舊的還在前面 11 份裡，一小時後輪掉。開機後先還原再起（樹放 `~/` 就沒這問題）。cron 掛法更糟：樹停著也照跑。
4. **還原到別的路徑**：`AUTOSAVE_DIR` 沒改的話，兩棵樹存進同一個資料夾、互相蓋 `latest`。實測時另設 `AUTOSAVE_DIR` 避開；env.sh 那格讓它跟著 `T` 改比較穩。
5. **存檔裡是硬連結**：沒變的檔在各份之間是同一個 inode；直接在存檔裡起樹，`history.jsonl` 這種原地追加的檔會把**每一份**舊存檔一起改掉。一律 `cp -a` 抄出來再起。
6. **同一秒存兩次**：初版腳本用秒當名字，同一秒第二次 `mv` 會把新的一份塞進舊的那份裡面；已改成撞名加 `-2`。五分鐘一次碰不到，手動連按才會。
7. **Claude 的信任提示**：這台 `~/.claude.json` 裡 `/tmp` 本身已被信任過（`hasTrustDialogAccepted: true`），底下所有路徑跟著算，所以 `/tmp/...` 的 ws 開畫面、直接開 claude 都沒跳提示；信任記在 `~/.claude.json`，不在 `/tmp`，清了、還原了都照算。`~/aos-run/ws` 這種新路徑第一次開畫面會跳一次（`claude -p` 那條路不跳，試驗場一直是這樣）；畫面停在信任選單時 cli_session 回 `TrustMissing`，人 `aos-agent open` 進去選一次就好。這次沒在 `~/` 新路徑實測。
8. **eca 對話本體不在樹裡**：claude 在 `~/.claude/projects/<ws 路徑>/<id>.jsonl`、codex 在 `~/.codex/sessions/`；樹裡只有 `session.txt`、`.session_home` 與指過去的 symlink。所以只存樹、同路徑還原能 `--resume` 接上；`~/.claude` 被清（或 CLI 自己清舊對話）就只剩 reseed。
9. **daemon 的 cwd 是定義資料夾**（`/proc/<pid>/cwd`＝`defs/root`、`defs/llm`），子 loop 的 cwd 是自己的 stack、eca 的 python 是自己的定義資料夾：把定義資料夾整個換掉（`rm -rf` 再抄）時，跑著的行程 cwd 會變成已刪的目錄——要換定義先停樹。
10. **背景起的 daemon 不會跟著 `wsl.exe` 那個視窗死**：這次每一步都是 `wsl -d Ubuntu -- bash -lc …` 開完就關，用 `setsid nohup` 起的樹一直活著。但那時 VM 一直有別的 session 撐著；**所有視窗都關掉後 WSL 會不會自己停**（`vmIdleTimeout` 之類）沒實測、這台 `.wslconfig` 只有 `networkingMode=mirrored`。停了的話樹放 `/tmp` 下次開機就是空的，放 `~/` 只是睡著、下次起自己醒。

## 放 /mnt/c 那一版（做到一半改方案，留作「為什麼不走這條」）

- 只讀了設定、沒建 `C:\tmp\aos-agents-trial\`：`/mnt/c` 是 9p drvfs（`aname=drvfs;…;cache=5`），**沒有 `metadata` 選項**＝Linux 的執行位元、chmod 存不進去（從掛載選項推、沒實測）；cli_session 檔頭已記 `/mnt/c` 上 AF_UNIX bind 不了（所以畫面 socket 搬去 `/tmp/aos-tty-<uid>/`）。
- 表上路徑相對 daemon 的 stack 存：stack 在 Linux、定義在 `/mnt/c` 時會存成 `../../../mnt/c/…`，stack 一換深度就斷（打絕對路徑才原樣存）。
- 頂層原本的第 2、3、7 條（`/mnt/c` 速度、CRLF／BOM／大小寫／執行位元、`/mnt/c` 路徑的信任提示）隨改方案取消，沒驗。

## 沒驗到的

- 真的重開 WSL 看 `/tmp` 被清（照指示不 `wsl --shutdown`；靠 tmpfiles 設定與「/tmp 最舊的檔就是今天開機那刻」推）。
- 關掉所有視窗後 WSL 會不會自己停、停了 daemon 怎樣（坑 10）。
- 30 天清理（坑 1）。
- `~/` 新路徑的信任提示（坑 7）。
- codex 那隻（這次只有 claude haiku）；五分鐘間隔本身（測試用 20 秒，腳本一樣）。

## 殘留（都停著、沒刪）

`/tmp/aos-run-trial/`（主樹，五列 sleeping）、`~/aos-run-trial-save/`（13 份存檔）、`/tmp/aos-run-trial-race/`＋`/tmp/aos-run-trial-race.err`（邊跑邊抄那批）、`/tmp/aos-run-trial-r2/`＋`/tmp/aos-run-trial-r2-save/`（換路徑還原那棵與它的存檔）、`~/aos-run-trial-bench/`、`/tmp/aos-run-trial-bench/`、`/dev/shm/aos-run-trial-bench/`（測速三棵）、`/tmp/aos-trust-probe/`（空）、`/tmp/line-cdrive/`（這條線的 clone）；`~/.claude/projects/-tmp-aos-run-trial-ws/`、`-tmp-aos-run-trial-r2-ws/`（eca 的對話本體）。
