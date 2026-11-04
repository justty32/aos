# 2026-11-02 試驗場：daemons/main（普通 daemon 掛 loop）＋ bob 直接掛上去（execs）

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜前情：[11-01 試驗場 bob](../01/playground-bob/README.md)、[11-02 試驗場 cathy](playground-cathy/README.md)｜程式：[aos-daemon](../../../impls/aos-daemon/README.md)（`execs`、信箱模式）、[aos-daemon-ctl](../../../bin/README.md)｜條文：[N-28、N-54](../../../docs/NORMS/04-基礎設施-loop與daemon.md)｜場地 `~/code/playground/`（WSL，不在 git）

本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-02，逐字）

> 接下來是在~/code/playground/daemons，弄一個普通的daemon，掛loops的。然後把agents/bob改成可以掛著的。或是不用改，看看daemon能不能直接掛aos-exec的

## 做了什麼（頂層代做，可翻案）

建的檔（都在 `~/code/playground/`；repo 程式沒動，`agents/bob` 沒動）：

- `daemons/main/_entry.json`＝`["aos-daemon", "daemon.json"]`（argv[0] 直接寫程式，不用 sh）。
- `daemons/main/daemon.json`＝開 ctl／state 兩扇窗、**信箱模式**（aos-daemon-ctl 要它），`loops` 掛一個 `clock`：每 5 秒跑一次 `date "+%F %T 還在跑"`，附加到它小格的 `clock.txt`。單子寫在同一份檔的 `/loops/clock/body`，`exec` 用 `"daemon.json#/loops/clock/body"` 指進去；輸出路徑寫 `{"$env": "AOS_STACK", "$path": "clock.txt"}`，不寫死小格位置。

### 結論：daemon 能直接掛 aos-exec，bob 不用改

- 用 exec 型子項 `execs`（10-30）：目標寫成 `[目標, 參數...]`，題目放在參數裡——`["../../agents/bob", "--", "題"]`，daemon 起它＝`aos-exec ../../agents/bob -- 題`，跟手動叫一樣（相對路徑從 daemon 的 cwd＝`daemons/main/` 算）。
- 給題：`aos-daemon-ctl add ../agents/bob -- "題"`（XXX 從呼叫處的 cwd 轉絕對）。
- bob 的工作區：子項沒寫 `ws`＝繼承 daemon 的 `AOS_WS`；在 `ws/` 裡 `aos-exec ../daemons/main` 時就是 `ws/`，bob 的 `--add-dir` 照舊拿到它。bob 的 stack 是它在 daemon 底下的小格。

### 用的時候會碰到的事（實測）

1. **bob 的 stdout 看不到**：daemon 把子項的 stdout 丟掉（N-28），結果只看他寫進工作區的檔、小格的 `stderr.txt`；結束碼看 daemon 的 log（`aos-daemon --enable-logs`），`ls` 只列還在跑的。所以題目要叫他寫成檔。
2. 子項結束後不留名單，同名直接再 `add` 就會重跑（[state 窗](state-window/01-使用者原文-11-02-逐字.md#決定11-02-晚使用者實作中陸續裁的)）。
3. **用 ctl 停 daemon 之後，`daemon_ctl.json` 會留著**：下次起來第一圈就讀到 `stopped`、馬上結束。要嘛停完刪掉 `.stack/daemon_ctl.json`，要嘛用 Ctrl-C 停（不留檔）。
4. daemon 重起時，做完的 bob 不會回到表上（他不在 daemon.json 裡、`adopt` 只接還活著的）；clock 照 daemon.json 重新起，`clock.txt` 接著附加。

### 給使用者的指令

```sh
# 視窗一：起 daemon（會擋著；Ctrl-C 停）
cd ~/code/playground && source env.sh && cd ws
aos-exec ../daemons/main

# 視窗二：看、掛、拿
cd ~/code/playground && source env.sh && cd ws
export AOS_DAEMON_STACK=$PWD/.stack
aos-daemon-ctl ls                       # 名單：名字、loop/exec、phase、pid、結束碼
tail -f .stack/loops/clock/clock.txt    # clock 每 5 秒一行

# 給 bob 題目（掛上）
aos-daemon-ctl add ../agents/bob -- "在 env:AOS_WS 寫一首詩，詠桃花，檔名 peach.txt。"
aos-daemon-ctl ls                       # bob exec running；跑完就從表上消失
cat peach.txt                           # 結果
cat .stack/loops/bob/stderr.txt         # 出錯時看這裡

# 再問一題／拿掉
aos-daemon-ctl add ../agents/bob -- "下一題"   # 做完的同名可直接再 add；rm 只用來停還在跑的
aos-daemon-ctl rm clock                 # 拿掉 clock；放回：
echo '{"loops_added": {"clock": {"exec": "daemon.json#/loops/clock/body", "interval_ms": 5000}}}' | aos-post send .stack/loops_ctl_mailbox

# 停 daemon：視窗一 Ctrl-C；或
echo '{"stopped": true}' > .stack/daemon_ctl.json   # 停完記得 rm .stack/daemon_ctl.json，不然下次一起來就停
```

### 代定清單

1. **daemon 放 `daemons/main/`**：`daemons` 當成放好幾個 daemon 的資料夾，這個叫 main。
2. **掛的 loop＝`clock`，每 5 秒用 `date` 附加一行**（`stdout_append`）；不用 aos-tick，不用 sh。
3. **clock 的單子寫在 daemon.json 裡、用 `daemon.json#/loops/clock/body` 指**：單子裡的 `{"$env": "AOS_STACK"}` 要在子 loop 每次跑時才解、拿到 clock 自己的小格；直接把單子放進 `exec`，daemon 會先解，拿到的是 daemon 自己的 stack。
4. **開信箱模式**：aos-daemon-ctl 的 `add`／`rm` 只認信箱；不開 `loops_ctl.json`。
5. **daemon 沒寫 `max`**（一直跑）、`interval_ms` 用預設 200。
6. **bob 用 `execs` 直接掛、不另做可掛的 bob**：能不改就不改。
7. **bob 的目標寫相對路徑**，不寫死 `/home/guanyu/...`。
8. **bob 子項不寫 `ws`**：繼承 daemon 的工作區（`ws/`），跟手動叫 bob 時一樣。
9. **daemon 的 stack 就是 `ws/.stack/`**（照現有用法 `cd ws && aos-exec ...`）。

### 方向題

- 「把 agents/bob 改成可以掛著的」若是指**一直開著、一題一題等**，那是另一種掛法：常駐版見 2026-11-02-resident-bob。
