# wf/tree：`.stack` 那棵樹的定義（子 daemon，不帶時鐘，只帶清道夫）

← [wf](../)｜規劃：[02-規劃 線 5](../../proto8/thinking/2026-11/22/工作區與stack-1122/02-規劃.md#線-5根那份小定義進-repo)

`root/` 是 repo 那棵（表上 `repo-aos`）那台 daemon 的定義（資料夾名字還叫 `root`，但它已經不是根，見下一段）：表上只有 `_sweeper`，agent 之後用 `aos-agent ctl add` 掛上去（表上存相對 `.stack` 的路徑）。`.stack` 被 git 忽略、每台各有各的，不跟著 git 搬（使用者 11-23）；這份定義跟著 git 走，兩台起的都用它。llm kernel 與權限站**不在這裡**，各台自己跑、放在 repo 外（使用者 11-22 決定 E）。

**11-23 起，這份定義是 `~/aos-home` 那棵樹底下的一台子 daemon**（表上那列叫 `repo-aos`；stack 兩台都是 `~/aos-home/.stack/procs/repo-aos`：公司那台 11-24 起、家機 11-24 晚起，兩台的 repo 裡都已經沒有 `.stack`）：使用者 11-23「repo aos這個樹會變成~/aos-home底下的一個proc」。`AOS_LLM_KERNEL`（公司那台另有 `CLAUDE_CONFIG_DIR`）記在那一列的環境值裡，子 daemon 傳給底下每一隻。**鐘只在 `~/aos-home` 的根**：根的 `_clock` 寫 `~/aos-home/.stack/clock`，`AOS_CLOCK` 由上層傳下來，所以這份定義 11-23 起拿掉了 `_clock` 那列與 `.env` 的 `AOS_CLOCK`（之前它一直多寫一份 `~/repo/aos/.stack/clock`，底下的 agent 聽的都是根的，那份沒人讀；使用者 11-23「可以拿，不用馬上重啟」）。公司那台 11-23、家機 11-24 晚都已這樣建好。起樹只起 `~/aos-home` 的根，怎麼掛、怎麼起停，看[每台設定說明書](../workflows/dev-env/03-換機.md)：

```sh
cd ~/aos-home && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK -u AOS_KERNEL -u AOS_LLM_KERNEL aos-exec --stack .stack root
```

**這份定義不能再單獨起成一台根**（11-23 起）：單獨起照樣起得來、不印任何警告，但底下的 agent 拿不到 `AOS_CLOCK`，on_clock hook（收信通知 mail_notify、context 收尾 context_wrap 等）都不跑。更容易看錯的是起過舊定義的 stack：表上留著的舊 `_clock` 列會被接回、照樣每秒寫 `.stack/clock`，看起來鐘在走，agent 還是拿不到（11-23 暫存樹實跑過）。

- **還沒改成這套的那台**（兩台都已改好：公司那台 11-23、家機 11-24 晚；這條留給舊樣子的機器）：pull 之後**先照說明書[「家機照做」](../workflows/dev-env/03-換機.md#家機照做從舊樣子改成同一套做一次)改成 `~/aos-home` 一套，再起樹**。以前那行 `cd ~/repo/aos && … aos-exec --stack .stack wf/tree/root` 不要再用。
- **真的得臨時單獨起**（還沒空改）：改起範本 `daemon-root`（它自己帶鐘），殼裡先 export 好 `AOS_LLM_KERNEL`：`cd ~/repo/aos && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack ~/aos-home/.stack/procs/repo-aos "$AOS_HOME/templates/daemons/daemon-root"`（11-23 暫存樹實跑過，底下拿到 `AOS_CLOCK`）。殼裡忘了 export 的話，範本 `.env` 那行預設會把 `AOS_LLM_KERNEL` 指到 `../llms`，agent 問腦就一直等。
- **已經掛在 `~/aos-home` 底下的那台**更別單獨起（會 `DaemonExists`，或在上面的根沒開時起成一台沒帶 alt 帳號、也沒鐘的獨立根）。
- **舊的 `_clock` 列要自己拿掉**：daemon 只在起來時讀一次 `daemon.json`，表上已有的列照記錄接回，所以改了定義、重起都不會讓它消失。下 `aos-daemon-ctl -d <repo 那棵的 stack> rm _clock` 一次就好（不用重起，暫存樹實跑過：拿掉後重起也不會回來）；留下的 `.stack/clock` 不再更新、沒人讀。

## 跟範本 `proto8/templates/daemons/daemon-sub` 的差異

11-23 拿掉鐘之後，它跟子 daemon 範本 [`daemon-sub`](../../proto8/templates/daemons/daemon-sub/README.md) 設定一樣（`daemon.json` 只有 `procs_requests` 與同一列 `_sweeper`，`.env` 只設 `AOS_HOME=${AOS_HOME}`，`_entry` 同一行 argv），差在：

- `.env`：第一行寫明是 `repo-aos` 那一列；多三行註解：`AOS_LLM_KERNEL` 從那一列的環境值來、故意不給預設（那一列忘了帶時，agent-fsm 第一次問腦就停下，`procs/<名>/stderr.txt` 寫 `agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set …`，不會指向不存在的資料夾默默一直等）、不要在這裡設 `AOS_KERNEL`（權限站是各台的）。
- `daemon.json`：展開排版（原本從家機舊樹 `~/aos-home/root/` 抄來的樣子），說明句寫明是 repo 那棵。
- `_entry`：說明句寫明由 `~/aos-home` 的根當 `repo-aos` 那一列起。
- 沒有範本的 `README.md`（這份就是）。

## 忘了 export 之後怎麼救

`AOS_LLM_KERNEL` 沒傳到時，agent 連續三次一起來就退出，表上會變成 `stopped`（原因欄只寫 `RunFailed … not restarting again`，代號要看它的 `stderr.txt`）。補上（11-23 起是 `repo-aos` 那一列的 `--envs AOS_LLM_KERNEL=…`，見說明書「常見錯誤」）、重起之後，它**不會自己醒**，要再下一次 `aos-agent -d ~/aos-home/.stack/procs/repo-aos ctl start <名>`；起來後先前排隊的問題會照樣答。
