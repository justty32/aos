← [教學入口](README.md)｜上一章 [01 開始前](01-開始前.md)｜下一章 [03 灌 kernel](03-灌kernel.md)

# 02 架 daemon（買一塊板子、開機）

**結論**：抄一份根 daemon 的範本、改一行讓它知道 kernel 會插在哪，`aos-exec root` 就開機了；`aos-daemon-ctl ls` 看表，`shutdown` 關機，再開機時上面的東西自己醒。

## 抄範本、先替 kernel 留位置（視窗 B）

```sh
cp -r $AOS_HOME/templates/daemon-root root
ls -A root
cat root/_entry
sed -i 's|^AOS_LLM_KERNEL=.*|AOS_LLM_KERNEL=${AOS_STACK}/procs/llm|' root/.env
grep '^AOS_' root/.env
```

你會看到：

```
.env
README.md
_entry
daemon.json
{"description": "Start the root daemon with stdout logs", "argv": ["aos-daemon", "--enable-logs", "daemon.json"]}
AOS_CLOCK=${AOS_STACK}/clock
AOS_LLM_KERNEL=${AOS_STACK}/procs/llm
AOS_HOME=${AOS_HOME}
```

- `_entry`＝這個資料夾「被執行」時跑什麼（資料夾＝程式）：這裡是起一台 `aos-daemon`。
- `.env`＝板子上每樣東西都繼承的環境變數。改的那行說「llm kernel 在板子自己的 `procs/llm`」——下一章就把 kernel 插在那裡。範本原本指「旁邊另一個專案」，所以要改。
- `daemon.json`＝表上出廠就有的兩列：`_clock`（時鐘）、`_sweeper`（清舊記錄）。

## 開機（視窗 A）

```sh
aos-exec root
```

前景跑著，印出狀態變化（一行一個 JSON）：

```
{"at": "2026-11-19T06:56:12.523+00:00", "name": "_clock", "phase": "running", "pid": 802752, "code": null, "signal": null}
{"at": "2026-11-19T06:56:12.524+00:00", "name": "_sweeper", "phase": "running", "pid": 802753, "code": null, "signal": null}
```

板子跑起來的樣子在 `.stack/`（沒給 `--stack` 時就是這個名字）。

## 看表（視窗 B）

```sh
aos-daemon-ctl -d .stack ls
ls .stack
```

```
_clock	running	802752	-	-	-
_sweeper	running	802753	-	-	-
# daemon: running (pid 802750)
# root daemon (no supervisor)
clock
procs
procs_requests
procs_state.json
state.json
state_flux.json
```

表的六欄：名字、狀態、pid、上次的退出碼、工作區、原因（沒有＝`-`）。最後兩行說板子自己活著沒、上面有沒有人管它（根＝沒有）。

## 關機、再開機

```sh
aos-daemon-ctl -d .stack shutdown
aos-daemon-ctl -d .stack ls
```

```
daemon at ~/code/aos-tut/.stack stopped (ctl seq 1); 2 procs asleep, they wake when it starts again
_clock	sleeping	-	143	-	-
_sweeper	sleeping	-	143	-	-
# daemon: not running (pid 802750 is gone); the table above is what it left
# root daemon (no supervisor)
```

視窗 A 的 `aos-exec` 這時自己結束了。表還在（`sleeping`＝睡著，記得自己是誰）。再在視窗 A 打一次 `aos-exec root`，視窗 B 看表：

```
_clock	running	803030	-	-	-
_sweeper	running	803031	-	-	-
# daemon: running (pid 803028)
# root daemon (no supervisor)
```

睡著的自己醒了，不用一個個叫。

**想直接起 eca_main**：板子開著（視窗 A 的 `aos-exec root` 別關），跳到 [05b 起 eca_main](05b-起eca_main.md)。上面改的 `.env` 那行對 eca_main 沒影響，留著就好。

<details><summary>關機兩次會怎樣</summary>

板子已經關了再 `shutdown`，退出碼是 1：

```
aos-daemon-ctl: error: DaemonMissing no aos-daemon running at ~/code/aos-tut/.stack (pid 802750 is gone)
exit=1
```

所以兩句關機指令別用 `&&` 串（第一句失敗，第二句就不跑）。視窗 A 按 Ctrl-C 也是關機，效果一樣。
</details>
