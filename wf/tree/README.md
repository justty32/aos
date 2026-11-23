# wf/tree：`.stack` 那棵樹的根定義（只帶時鐘與清道夫）

← [wf](../)｜規劃：[02-規劃 線 5](../../proto8/thinking/2026-11/22/工作區與stack-1122/02-規劃.md#線-5根那份小定義進-repo)

`root/` 是 `~/repo/aos/.stack` 那台根 daemon 的定義：表上只有 `_clock`、`_sweeper`，agent 之後用 `aos-agent ctl add` 掛上去（表上存相對 `.stack` 的路徑）。`.stack` 被 git 忽略、每台各有各的，不跟著 git 搬（使用者 11-23）；這份定義跟著 git 走，兩台起的都用它。llm kernel 與權限站**不在這裡**，各台自己跑、放在 repo 外（使用者 11-22 決定 E）。

**11-23 起，這份定義是 `~/aos-home` 那棵樹底下的一台子 daemon**（表上那列叫 `repo-aos`，stack 仍是 `~/repo/aos/.stack`）：使用者 11-23「repo aos這個樹會變成~/aos-home底下的一個proc」。`AOS_LLM_KERNEL`（公司那台另有 `CLAUDE_CONFIG_DIR`）記在那一列的環境值裡，子 daemon 傳給底下每一隻；這份定義沒改。公司那台 11-23 已這樣建好，家機還沒改。起樹只起 `~/aos-home` 的根，怎麼掛、怎麼起停，看[每台設定說明書](../workflows/dev-env/03-換機.md)：

```sh
cd ~/aos-home && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK -u AOS_KERNEL -u AOS_LLM_KERNEL aos-exec --stack .stack root
```

還沒改成這套的那台（家機 11-23），照舊在殼裡 export 好 `AOS_LLM_KERNEL` 後單獨起：`cd ~/repo/aos && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack .stack wf/tree/root`。已經掛在 `~/aos-home` 底下的那台別這樣起（會 `DaemonExists`，或在上面的根沒開時起成一台沒帶 alt 帳號的獨立根）。

## 跟範本 `proto8/templates/daemon-root` 的差異

- `.env`：拿掉 `AOS_LLM_KERNEL` 的預設行，換成註解。殼裡忘了 export 時，agent-fsm 第一次問腦就停下，`procs/<名>/stderr.txt` 寫 `agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set …`；不會指向不存在的資料夾默默一直等。「不要在這裡設 `AOS_KERNEL`」那行留著，理由改成權限站是各台的。
- `daemon.json`：內容一樣，只有排版不同（從家機舊樹 `~/aos-home/root/` 抄來，那份是展開排版）。
- 沒有範本的 `README.md`（那份講的是範本的 `../llms` 預設，這裡不適用）。

## 忘了 export 之後怎麼救

agent 連續三次一起來就退出，表上會變成 `stopped`（原因欄只寫 `RunFailed … not restarting again`，代號要看它的 `stderr.txt`）。補上 export、shutdown 根再起之後，它**不會自己醒**，要再下一次 `aos-agent -d .stack ctl start <名>`；起來後先前排隊的問題會照樣答。
