這份講清楚 aos-agent／aos-daemon-ctl 沒給 `-d` 時找哪台 daemon，以及人站在 agent 自己的夾裡時最短要怎麼打才跟它說得上話（試驗 02，11-18 在公司 WSL 用 haiku 實跑過）。

← [目錄](README.md)

使用者原話：「2.我記得stack沒指定的話，就是默認./.stack？那我想試試看cd到daemon stack / proc/ agent-1/，然後直接跟他agent say。」

## 結論（預設規則一句話）

**找 daemon 的順序是：`-d`（或 `--daemon`） ＞ 環境變數 `AOS_DAEMON` ＞ 目前所在資料夾裡的 `./.stack`。三樣都沒有就報 `DaemonMissing`。`AOS_STACK` 不算在內。** 你記得的「預設 `./.stack`」是對的，只是它排第三。

- 這條規則 `aos-agent` 和 `aos-daemon-ctl` 共用，程式在 `py/aos/daemon_ctl/table.py` 的 `find_daemon`。
- 「跟哪隻說」另外算：`-t`（或 `--target`） ＞ `AOS_AGENT`。兩樣都沒有就報 `TargetMissing`。
- 站在 agent 的夾 `~/aos-home/.stack/procs/ann/` 裡直接打 `aos-agent say hi`，會**被當成「對 `./.stack`」而找不到**，不會自動認出「我就在 ann 裡」。
- 站在那裡最短的打法：`aos-agent -d ../.. -t ann say …`。agent 的夾往上兩層，就是 daemon 的 stack。
- 站在樹根 `~/aos-home` 時，`-d .stack` 可以省掉，例如 `aos-agent -t ann say …`。

## 實跑：站在 agent 的夾裡

前提：樹照 [README 的「共同準備」](README.md#共同準備)起好，視窗 A 開著，`ann` 是 running。

```sh
cd ~/aos-home/.stack/procs/ann
```

**① 什麼都不帶**

```sh
aos-agent say hi
```

```
aos-agent: error: TargetMissing no target: add --target NAME, or export AOS_AGENT=NAME (or source using-aos-agent.sh NAME)
```

它先抱怨不知道要跟誰說。

**② 只帶名字**

```sh
aos-agent -t ann say hi
```

```
aos-agent: error: DaemonMissing no --daemon, AOS_DAEMON not set, and no .stack folder in the cwd (point it at the daemon's $AOS_STACK folder)
```

這就是「被當成對 `./.stack`」：這個夾裡沒有 `.stack`，所以找不到。`listen`、`ask`、`aos-daemon-ctl ls` 也都是這一行。

**③ 帶 `AOS_STACK` 也沒用**

```sh
AOS_STACK=$PWD aos-agent -t ann listen --last 1
```

結果一樣是 `DaemonMissing`。找 daemon 不看 `AOS_STACK`。

**④ 把 `-d` 指到 agent 自己的夾（常見的錯）**

```sh
aos-agent -d . -t ann say hi
```

```
aos-agent: error: StateMissing /home/你/aos-home/.stack/procs/ann/procs_state.json not found (daemon not started yet, or procs_state is off)
```

`-d` 要的是 **daemon 的** stack（裡面有 `procs_state.json`，也就是那張表），不是 agent 的 stack。這句錯誤訊息說「daemon not started yet」，其實是指錯了地方。

**⑤ 最短的正確打法**

```sh
aos-agent -d ../.. -t ann ask --timeout-s 120 "Reply with exactly: pong"
```

會看到 `pong`。`../..` 就是 `~/aos-home/.stack`。

**⑥ 想之後都不用帶**：先 export 一次，這個視窗之後隨便打：

```sh
export AOS_DAEMON=$(realpath ../..) AOS_AGENT=ann
```

```sh
aos-agent listen --last 1
```

會看到 `== #3`、`> Reply with exactly: pong`、`pong`。`cd /tmp` 之後再打也一樣，因為 `AOS_DAEMON` 存的是絕對路徑（所以要用 `realpath`）。如果寫成相對路徑 `AOS_DAEMON=../..`，換了資料夾就會指錯。

另一種寫法是 repo 附的 `source $AOS_HOME/lib/aos/apps/agent/using-aos-agent.sh ann`，之後可以直接打 `say …`、`listen`。注意它在 `AOS_DAEMON` 沒設時會設成 **`$PWD/.stack`**，所以要站在**樹根**才 source，站在 agent 的夾裡 source 會指錯（我讀程式看到的，沒實跑）。

## 實跑：站在樹根

```sh
cd ~/aos-home && source env.sh && aos-agent -t ann listen --last 1
```

不用 `-d` 就能用，因為樹根有 `.stack`。

## 實跑：誰優先

- 名字不在表上：`aos-agent -d .stack -t nobody say hi` 會看到下面這行：

  ```
  aos-agent: error: InstanceMissing nobody is not on the daemon table (removed with rm, exited 0, …; the stack may still be there: aos-agent ctl add with the same name to pick it up again)
  ```

- `AOS_DAEMON` 指到不存在的夾：`AOS_DAEMON=/nonexist aos-agent -t ann listen --last 1` 會看到 `aos-agent: error: DaemonMissing daemon folder not found: /nonexist`。**有 `AOS_DAEMON` 就不再看 `./.stack`。**
- 站在樹根、`AOS_DAEMON` 指另一棵樹（`~/aos-home2/.stack`，停著的）：`aos-agent ctl ls` 列出的是**那棵**的表，三列 sleeping。
- 同樣的狀況再加 `-d .stack`：列出的是**這棵**的表，`ann running`。**`-d` 贏過 `AOS_DAEMON`。**

## 常見卡點

- **`source env.sh` 會清掉所有 `AOS_*`**（`AOS_HOME` 除外）。所以先 export `AOS_DAEMON`、後 source env.sh，`AOS_DAEMON` 就沒了。要先 source，再 export。
- agent 自己的殼裡（claude 叫 Bash 時）本來就帶著 `AOS_DAEMON`（看 `.stack/procs/ann/claude/env.json` 的鍵名），所以 agent 在裡面打 aos-agent 不用 `-d`。人的視窗沒有這個變數。
- `-t` 寫在子指令前後都可以，但 `ctl ls` 不收 `-t`：`AOS_DAEMON=… aos-agent -t ann ctl ls` 會報 `ArgumentsBad ctl ls does not take --target`。

## 發現的問題

1. 站在 agent 的夾裡打 `-d .`，錯誤訊息說「daemon not started yet」，會誤導。其實是指成了 agent 的 stack，不是 daemon 的。試驗 07 也碰到同一句。
2. `using-aos-agent.sh` 在 agent 的夾裡 source 會把 `AOS_DAEMON` 設成 `<那個夾>/.stack`，不會提醒。這是讀程式看到的，沒實跑。
