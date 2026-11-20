# 「提供 hook 點」的介面：施工第 5 刀的 aos-loop 那一半（身體每跑一次的前後兩個點、旗標檔、四個點失敗都收工；範本接線沒做）

← [當天索引](README.md)｜設計 [aos-hook-plan-1120](aos-hook-plan-1120/README.md)（loop 層在 [06](aos-hook-plan-1120/06-loop層的點.md)，刀 5 在 [09b](aos-hook-plan-1120/09b-施工計劃-逐刀.md#刀-5loop-層的點)，對不上以 [12 採納表](aos-hook-plan-1120/12-採納表.md) 為準）｜使用者已答 [13](aos-hook-plan-1120/13-使用者已答.md)｜前幾刀 [k1](aos-hook-k1-1120.md)、[k2](aos-hook-k2-1120.md)、[k4](aos-hook-k4-1120.md)｜編譯線 [aos-pylib-k4-1120](aos-pylib-k4-1120.md)

線 aos-hook-k5-1120，11-20 公司 WSL，頂層派、線隊長做。依據（逐字在 13）：方向第 3 題「在 loop 層加通用的點」；待裁第 1 題「能攔」、第 2 題「四個點都跟著停」、第 11 題「用旗標檔」、第 12 題「before_run / after_run」、第 7 題 kernel「接」、第 14 題 kernel「一起搬」；11-20「舊的教學我都沒在用，現有的aos體系我也都沒在用。所以放心弄。」（不顧相容）。

## 結論

- **aos-loop 有了身體前後兩個點**：loop.json 選填 `on_before_run`、`on_after_run`（寫法同 `exec`）與 `on_before_run_if`、`on_after_run_if`（旗標檔路徑：檔在才跑）。順序、結束碼、環境變數照設計 06 的順序圖與 12 的改動（跳過推時間、退 0 後再讀 ctl、訊號優先、after 失敗誰的碼算數、`AOS_LOOP_RUN_SIGNAL` 空字串、跑完還原）。
- **四個點失敗都收工**（使用者「四個點都跟著停」，不是設計預設）：`on_start` 失敗＝身體不跑、以它的碼收工；`on_stop` 失敗＝本來要退 0 才改碼；錯誤行新代號 `PointFailed`。aos-daemon 不跟（見「替使用者做的選擇」1）。
- **aos-daemon 不收那四個鍵**（寫了＝`CfgBad`）。
- `loop_points.json` 的文字跟著改：`after_start`／`after_stop` 的 if_failed 換成新行為；`before_run`／`after_run` **保留 `not_fired_yet`**，句子改成「aos-loop 跑得動，範本還沒接」。
- **相依判斷：範本接線、旗標維護、kernel 接線、刪 hook_fire、agent_spec 寫四鍵都等第 3 刀**（agent 讀不到 `hook_points` 時 `aos-hook fire --agent` 對每個事件都是 `EventUnknown`；agent 與 kernel 的事件表還不收 `before_run`）。這幾項一行沒動，見「沒做的」。
- 暫存樹實跑（真 daemon、假腦、手接一隻 fsm agent）：沒旗標時 3 秒 60 次取樣看不到一支 `aos-hook`；掛 `before_run`（condition act、退 10）＝act 被攔 6 次、工具沒被叫，拿掉後 act 跑、答案回來；`after_run` 有發；壞的 `before_run` hook 與壞的 `after_start` hook 各自讓 agent 停下（舊 aos-loop 下壞的 after_start 照樣起來）。沒人掛時每圈多花的時間量不出來（在雜訊內），數字見「耗時」。

## 改了哪些檔

| 檔 | 新／改 | 一句話 |
|---|---|---|
| `cpp/aos-loop/include/aos/loop.hpp` | 改 | `PointFailed` 代號；`runs_env` 等四個環境變數名；`Defaults::run_points`；鍵表註解；四個成員；`PointRun`、`run_point`、`point_on`、`before_point`、`after_point`；`run_side` 回結果、`stop_side` 回碼 |
| `cpp/aos-loop/src/engine/points.cpp` | 新 | 四個點怎麼跑（`run_side`、`stop_side` 從 loop.cpp 搬來，加 before／after 兩點與 `EnvSet` 還原環境）；156 行 |
| `cpp/aos-loop/src/engine/loop.cpp` | 改 | `main_loop` 插兩個點、`on_start` 失敗收工、`end` 用 `stop_side` 回的碼；`RunFailed` 那行移到 after 之前印 |
| `cpp/aos-loop/src/engine/config.cpp` | 改 | 解四鍵（兩個進 exec 那組、兩個 `_if` 進 `resolve_keys`）、驗 `_if`、`run_points` 是 false 時寫了就 CfgBad |
| `cpp/aos-loop/src/main.cpp` | 改 | `--help` 加四鍵與 PointFailed |
| `cpp/aos-loop/src/engine/engine.hpp` | 改 | 檔頭的檔表加 `points.cpp` 一行（只有註解） |
| `cpp/aos-loop/tests/test_run_points.py` | 新 | 17 支 |
| `cpp/aos-loop/tests/test_on_start_stop.py` | 改 | 「on_start 失敗只 warning」換成收工；加起不來、on_stop 失敗兩種；on_stop 逾時改成非 0 |
| `cpp/aos-loop/README.md`、`docs/01-用法.md`、`03-元素等.md`、`04-建置與測試.md` | 改 | 新一段、順序圖、錯誤代號、測試清單 |
| `cpp/aos-daemon/src/daemon/daemon.cpp` | 改 | `daemon_defaults()` 設 `run_points = false` |
| `cpp/aos-daemon/tests/test_run_points_refused.py` | 新 | daemon.json 寫四鍵＝CfgBad；daemon 的 on_start 失敗照舊 warning |
| `cpp/aos-daemon/README.md` | 改 | 一句 |
| `py/aos/apps/hook/loop_points.json` | 改 | description、兩個 if_failed、兩個 not_fired_yet 的句子 |

檔都在任務書領地內；沒有刪檔。`loop.hpp` 改前已 363 行（公開標頭，註解為主），現 405 行；新的程式放進新檔 `points.cpp`，`loop.cpp` 從 268 降到 246 行。

## 新舊對照

| 情況 | 改前 | 改後 |
|---|---|---|
| loop.json 寫 `on_before_run` | 當沒看到 | 每次跑身體前跑；退 10＝跳過這一圈 |
| `on_start` 退 3 | `aos-loop: warning: on_start … exited 3`，照樣開跑 | `aos-loop: error: PointFailed on_start … exited 3`，身體不跑、退 3，on_stop 照跑 |
| `on_stop` 退 4、本來退 0 | warning、退 0 | `PointFailed on_stop …`、退 4 |
| `on_stop` 退 4、本來退 7 | warning、退 7 | 同左 |
| daemon.json 寫 `on_before_run` | 當沒看到 | `aos-daemon: error: CfgBad on_before_run is not taken by aos-daemon …` |
| daemon 的 `on_start` 失敗 | warning | 同左（不變） |

## 證據

### aos-loop、aos-daemon 的測試

- `cpp/aos-loop/tests` 33 → 52 支 OK（新 `test_run_points.py` 17 支；`test_on_start_stop.py` 多 2 支、改 2 支）；`cpp/aos-daemon/tests` 141 → 143 OK。
- **證明會紅**：把新的兩支測試檔放在指到基準複本 `bin/` 的殼裡跑（`red.sh`）＝舊 aos-loop 下 46 支有 13 failures、10 errors：`test_run_points` 17 支裡 16 支紅（只有「沒寫四鍵」那支兩邊都綠）、`test_on_start_stop` 改過的 4 支紅。

### 暫存樹實跑

`~/.aos/scratch/aos-hook-k5-1120/exp_run.py`（`exp.sh mine`；輸出 `exp-mine.txt`）：抄 start-api、llm kernel 加一個假腦（收到使用者的信先叫 probe 工具、拿到工具結果再回一句）、根 daemon＋llm 真的起；編一隻 `std.fsm()` 的 agent `a`，**手改它的 loop.json** 接兩個點（`aos-hook fire -q --points $AOS_HOME/lib/aos/apps/hook/loop_points.json --list <定義>/loop_hooks.json --field-file stage=$AOS_STACK/stage.txt --field-default stage=idle before_run`，after 帶 `next_stage`；`_if`＝`$AOS_STACK/hook_before_run.flag`、`hook_after_run.flag`）。旗標檔由腳本手建手刪（第 3 刀之後是 `hook add` 的事）。

```
NO FLAGS: aos-hook processes seen in 60 samples over 3 s: 0
  hold.log / seen.log lines: 0 0
HOLD ACT: before_run hook blocked 6 times; first event {'event': 'before_run', 'hook': 'hold_act', 'stack': '…/procs/a', 'counter_runs': 20, 'stage': 'act'}; stage now act; probe called 0 times; state.phase running
AFTER_RUN: fired 6 times; last two […{'counter_runs': 18, 'code': 0, 'signal': None, 'elapsed_ms': 69, 'next_stage': 'wait'}, {'counter_runs': 19, 'code': 0, 'signal': None, 'elapsed_ms': 68, 'next_stage': 'act'}]
RELEASED: answer -> ANSWER after tool: probe of a ; probe called 1
FLAGS GONE: aos-hook processes seen in 60 samples: 0 ; seen.log grew by 0
BEFORE_RUN FAILS: row a phase=stopped reason=failed while running: exited with code 1: aos-loop: error: PointFailed run 36: on_before_run loop.json#/on_before_run exited 1
```

- `before_run` 只在 stage＝act 時比中（`condition: act`），退 10 擋了 6 次（約 2 秒、間隔 300 ms），probe 一次都沒被叫；hook 從清單拿掉後下一圈 act 就跑、答案回來。
- `after_run` 帶 `counter_runs`、`code`、`signal`（null）、`elapsed_ms`、`next_stage`。被攔的圈不發 after（hold 6 次時 after 的 counter 停在 19、hold 從 20 起）。
- 表上的 `state.json` 在被攔時仍寫著 `running`：state 窗本來就「running／waiting 互換不算變動、不重寫」（11-02），loop 被跳過的圈沒寫新的一份，這是舊規矩不是這刀的。
- 「四個點都跟著停」實跑兩種：**壞的 before_run hook**（`boom.sh` 退 3、on_error 預設 stop → `aos-hook` 退 1）→ 上面最後一行，agent 停在 stopped；**壞的 after_start hook**（agent `b` 用 `hooks={"bad": {"event": "after_start", …}}` 編，走今天的 `hook_fire`）：

```
（改後）AFTER_START FAILS: row b phase=stopped reason=failed to start: exited within 3s of wake/start (code 1): aos-loop: error: PointFailed on_start loop.json#/on_start exited 1
  stderr of b: ['bad after_start hook', 'hook_fire: error: HookFailed hook bad (event after_start) failed: exited 3', 'aos-loop: error: PointFailed on_start loop.json#/on_start exited 1']
（改前，base 複本同一支腳本 only-start）AFTER_START FAILS: row b phase=running reason=None
  stderr of b: [… 'aos-loop: warning: on_start loop.json#/on_start exited 1']
```

- 樹留在 `/tmp/k5-run-s0y2k9mv`（改後）、`/tmp/k5-run-sd6zihhf`（改前）；行程用 daemon shutdown 收掉，事後 `pgrep` 沒有這兩棵樹的行程。

### 耗時

量法：`~/.aos/scratch/aos-hook-k5-1120/measure.py`（`measure.sh mine 2000 15`，輸出 `measure-mine.txt`）：裝好的 `bin/aos-loop`、身體 `/bin/true`、`interval_ms: 0`、窗全關，`--max 2000` 跑完量總時間除以次數；兩份 loop.json 輪流跑 15 輪取中位數——`plain` 沒有四鍵；`wired_no_flag` 接了 `aos-hook fire` 的兩個點與兩個 `_if`、旗標檔不在。

| 情況 | 每圈 |
|---|---|
| `plain`（對照：起一次 `/bin/true` 的身體） | 659.8 µs（最快 622.9） |
| 接了兩個點、旗標檔不在（＝沒人掛） | 657.0 µs（最快 618.3） |
| **差（沒人掛時每圈多花的）** | **−2.8 µs：量不出來，在雜訊內**（理論上是兩次 `access()`，設計 06 量過看檔約 0.84 µs） |
| 旗標檔在、清單是空的（每圈起兩支 `aos-hook`） | 54.1 ms |

- 機器負載 1.5 時量的。先前一輪在負載 13（兩份全套測試同時在跑）量到 +28.3 µs，最快的兩個差 110 µs，也是雜訊。
- 實跑那棵樹：沒旗標時 3 秒取樣 60 次，`pgrep -f "aos-hook fire"` 一次都沒看到；設計要的「沒人掛時不多起行程」成立。

## 沒做的與為什麼（相依）

設計 09 的總表寫刀 5「依賴 3、4」。第 4 刀（`aos-hook`）已交；第 3 刀（切到宣告）沒做。照任務書只做不相依的部分。卡在第 3 刀的：

| 沒做的 | 卡在哪 |
|---|---|
| 六份範本 loop.json（agent-fsm、agent-python、eca-claude、eca-pi、start-api/ann、start-eca/ann、reviewer）接四鍵、起停改 `aos-hook fire --agent` | `aos-hook fire --agent` 讀定義夾 `interfaces.json` 的 `hook_points`，今天沒有一份定義有（第 3 刀才加），對每個事件都是 `EventUnknown`；而且 agent 的事件表 `hooks.EVENTS` 不收 `before_run`，`hook add --event before_run` 掛不上 |
| `agent_spec` 的 `_Loop.json()` 寫四鍵、拿掉 `HOOK_FIRE` | 同上（編出來的接線要能發才有意義）；`_Loop` 結構沒動，之後照編譯線說的在 `json()` 裡多寫幾行就好 |
| 旗標維護（`aos-agent hook add／rm／reset`、`self_hook`、`aos-hook fire --agent after_start`、`aos-hook check --agent` 對旗標） | 在 `agentlib/hooks.py`、`apps/agent/hook.py`、`apps/hook/main.py`，都在 k2b 線手上；也要等點掛得上（第 3 刀） |
| procs-kernel 的 loop.json 接 loop 層的點（使用者第 7 題「接」） | kernel 自己的事件表（`kernel/hooks.py` 的 `EVENTS`，三個點）不收 `before_run`：清單寫了 kernel 每輪都 HooksBad；要等 kernel 讀宣告並把 loop 那份併進來（第 3 刀＋第 14 題「一起搬」）。另外 kernel 的清單在 kernel.json 裡、經指示詞解（F13），`aos-hook --list kernel.json` 看到的是沒解的；誰對 kernel 的旗標設計沒寫 |
| 刪 `py/tools/agent/hook_fire/` | 範本起停還靠它；換成 `aos-hook fire --agent` 之後才能刪 |
| `refs_check.py` 跟著新兩鍵查檔（F15）、`stack.gitignore` 擋兩個旗標（F14） | 接線之後才有人寫這兩鍵與旗標；不在領地 |
| 條文與附錄 4（NORMS/04 的「兩格出問題只印一行 warning」、CONVENTION 三份的 hook_fire） | 要點頭；見「要別線或頂層補的字」 |
| `--field-default` 用 `{"$ref": "fsm.json#/start", "$prefix": "stage="}` 能不能併用（12 列為沒核對） | 只有範本接線用得到；實跑用的是寫死的 `stage=idle` |

## 要別線或頂層補的字（本線 claim 不到或不在領地）

- `py/tools/agent/hook_fire/_entry` 檔頭（k2b 手上）：「aos-loop 只把它當一行 warning，不擋 agent 起停。」→「11-20 起 aos-loop 把它退非 0 當成 on_start／on_stop 失敗：on_start＝agent 起不來（PointFailed）、on_stop＝本來要退 0 的改成它的碼（使用者「四個點都跟著停」，線 aos-hook-k5-1120）。」
- `py/aos/apps/hook/README.md` 第 9 行（k2b 手上）：「`before_run`、`after_run` 先宣告、標 `not_fired_yet`（aos-loop 還沒接）」→「…標 `not_fired_yet`（aos-loop 已能跑 loop.json 的 `on_before_run`／`on_after_run`，範本還沒接）」。
- `docs/NORMS/04-基礎設施-loop與daemon.md` 第 7 行（要點頭）：「兩格出問題只印一行 warning，不擋起停、不改結束碼；aos-daemon 繼承 aos-loop，daemon.json 寫了也照跑」→「出問題＝收工：on_start 失敗不開跑、on_stop 失敗而本來要退 0 就改碼（11-20 使用者「四個點都跟著停」）；aos-daemon 照舊只一行 warning」，並加 `on_before_run`／`on_after_run`／兩個 `_if` 一句。
- `py/aos/apps/agent/docs/06-hook.md` 的 after_start／after_stop 兩列、`knowledge/aos/cli/hook.json`：今天沒寫失敗會怎樣，不用改；第 3 刀接線時一起寫「hook 失敗 agent 會停」。

## 跟設計對不上處

- 設計 06 寫「`on_start`／`on_stop` 照 11-11 只當 warning」，是設計預設；使用者第 2 題選「四個點都跟著停」，照使用者。
- 設計沒寫錯誤行的代號：新加 `PointFailed`（見選擇 2）。
- 設計 09b 列「`cpp/aos-daemon/README.md`、`tests/test_stop_cause.py`：一句；hook_fire 換 aos-hook」：README 加了一句；`test_stop_cause.py` 的 hook_fire 換 aos-hook 要等 `--agent` 能用（第 3 刀），沒動。
- 09b 驗收「`grep -rn hook_fire` 只剩歷史紀錄」：沒做（hook_fire 還在用）。

## 替使用者做的選擇（設計沒寫到的，都選最小）

1. **aos-daemon 的 on_start／on_stop 失敗照舊只 warning**：使用者第 2 題問的是「agent 要不要跟著停」，daemon 是管理員，設計 06 也寫「它今天收 on_start／on_stop，那兩個照舊」；`Defaults::run_points` 一個開關同時管「收不收新四鍵」與「起停失敗停不停」。要 daemon 也停＝把 `daemon_defaults()` 那行拿掉一半。
2. **錯誤行代號 `PointFailed`**（四個點共用；`RunFailed` 留給身體）。碼：退非 0＝那個碼；逾時＝那次的碼（0 時當 1）；起不來＝1。
3. **`on_stop` 失敗**：本來要退 0 才改成它的碼（照 after_run 的規矩）；本來就非 0＝一行 warning、碼不變。跑的期間收到訊號＝不算它失敗。
4. **`on_start` 失敗**：state 寫 done、`AOS_LOOP_CAUSE`＝`error`、on_stop 照跑（設計「跟身體失敗同一條路」）。
5. **`_if` 寫了卻沒寫對應的點＝CfgBad**（寫什麼就做什麼）；`_if` 寫 null＝沒寫；相對路徑照 cwd（同 exec 的目標）。
6. **daemon.json 寫了四鍵之一，連 `null` 也算 CfgBad**（設計「寫了就是設定錯」）。
7. **`on_after_run` 退 10 不特別處理**：after 不能攔，非 0 一律當失敗。
8. **`not_fired_yet` 留著**：`fired()` 的意思是「今天有東西在發」；aos-loop 跑得動了但沒有範本接，`test_hook_points_match` 拿它跟 `hooks.EVENTS` 比，拿掉就要先動 agent 的事件表（第 3 刀）。只改句子。
9. 沒人掛時的成本用 `access(F_OK)` 看檔，每個點每圈一次；旗標檔存在而清單是空的＝照起 `aos-hook`（設計「白起一支，不會出錯」）。
10. 實跑沒有接範本、沒有動旗標維護：用手接的 loop.json 與手建的旗標檔代替，紀錄寫明。

## 跟別線有沒有撞檔

- 本線改的檔都 claim 到（見收尾）。想加字的 `hook_fire/_entry`、`apps/hook/README.md` 被 aos-hook-k2b-1120 claim 著，沒等、沒 `--force`，字寫在上面。
- 工作樹裡 k2b、aos-pylib-k5 沒交的改動沒碰、沒抄進複本（複本＝`git archive` 基準 commit＋本線的檔）。
- **給 k2b 的提醒**：這刀裝上之後，agent 的 `after_start` hook 失敗（`hook_fire` 退 1）＝agent 起不來；k2b 若有測試靠「壞的 after_start 只 warning」會變。全套測試裡沒有（見下）。

## 全套測試

兩份乾淨複本：`base`＝`git archive 726c30ba1`（開工時 HEAD）、`mine`＝同一個 commit 疊本線的檔（工作樹裡別線沒交的改動沒抄）；各自在複本裡跑 `install.py`（**含 C++ 全家編譯，mine 編得過**）、清掉 `AOS_*` 後逐夾跑 unittest，共 79 夾（`suite.sh`、`cmp.sh`；結果 `suite-base.txt`、`suite-mine.txt`，log 在 `logs-*`）。

| 夾 | base | mine |
|---|---|---|
| `cpp/aos-loop/tests` | 33 OK | 52 OK（＋本線 19） |
| `cpp/aos-daemon/tests` | 141 OK（skip 4） | 143 OK（skip 4；＋本線 2） |
| `py/tests/apps/eca` | 227，**1 failure**（`test_pi…test_10_live_mail_false_waits_for_the_next_turn`：第二封信趕上了同一輪，負載下的時間題；本線沒碰 eca） | 227 OK |
| 其餘 76 夾 | — | 逐夾支數與結果相同（`py/tests` 兩邊 721 OK skip 1；agent-fsm 215；兩邊都退 5 的 `templates/kernel/tests`、`templates/tests/image-move-check` 是 0 支，不是 unittest，同前幾刀） |

沒有因為「on_start 失敗會收工」而紅的既有測試（全套裡沒有測試靠「壞的 after_start 只 warning」）。

## 收尾

- 交件：見 commit；claim 交件時放掉。沒 push；沒在 `~/repo/aos/proto8` 跑 `install.py`（**改的是 C++：活樹要 install 換 `bin/aos-loop`、`bin/aos-daemon` 才吃到**，要使用者點頭；裝了之後 agent 的壞 after_start hook 會讓它起不來）。
- 叫模型：沒有（假腦）。
- 暫存：`~/.aos/scratch/aos-hook-k5-1120/`（`base`、`mine` 兩份複本、`dev`〔只有 cpp/ 的快編〕、`red`〔舊 binary 跑新測試的殼〕；腳本 `setup.sh`、`mine.sh`、`suite.sh`、`cmp.sh`、`dev.sh`、`devtest.sh`、`red.sh`、`measure.py`／`.sh`、`exp_run.py`／`exp.sh`、`edit_points.py`；結果 `suite-*.txt`、`logs-*`、`measure-mine.txt`、`exp-*.txt`）；TMPDIR 在 `/tmp/aos-hook-k5-1120-*`；實跑樹 `/tmp/k5-run-*`、量測 `/tmp/k5-measure-*`。都沒刪。
