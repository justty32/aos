# wf/tree：`_stack` 那棵樹的根定義（只帶時鐘與清道夫）

← [wf](../)｜規劃：[02-規劃 線 5](../../proto8/thinking/2026-11/22/工作區與stack-1122/02-規劃.md#線-5根那份小定義進-repo)

`root/` 是 `~/repo/aos/_stack` 那台根 daemon 的定義：表上只有 `_clock`、`_sweeper`，agent 之後用 `aos-agent ctl add` 掛上去（表上存相對 `_stack` 的路徑，兩台的 repo 都在 `~/repo/aos`，換台照樣對）。llm kernel 與權限站**不在這裡**，各台自己跑、放在 repo 外，由起根的殼 export `AOS_LLM_KERNEL`、`AOS_KERNEL` 指過去（使用者 11-22 決定 E）。

怎麼設殼、怎麼起 llm kernel、怎麼換台，看[換機說明書](../workflows/dev-env/03-換機.md)；這裡不重寫步驟，只記起根那一行：

```sh
cd ~/repo/aos && env -u AOS_DAEMON -u AOS_STACK -u AOS_CLOCK aos-exec --stack _stack wf/tree/root
```

`AOS_HOME`、`AOS_LLM_KERNEL`（與有權限站時的 `AOS_KERNEL`）要在這個殼裡已經 export，根會傳給底下每一隻；改了 export 要 shutdown 根再從新殼起才生效。

## 跟範本 `proto8/templates/daemon-root` 的差異

- `.env`：拿掉 `AOS_LLM_KERNEL` 的預設行，換成註解。殼裡忘了 export 時，agent-fsm 第一次問腦就停下，`procs/<名>/stderr.txt` 寫 `agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set …`；不會指向不存在的資料夾默默一直等。「不要在這裡設 `AOS_KERNEL`」那行留著，理由改成權限站是各台的。
- `daemon.json`：內容一樣，只有排版不同（從家機舊樹 `~/aos-home/root/` 抄來，那份是展開排版）。
- 沒有範本的 `README.md`（那份講的是範本的 `../llms` 預設，這裡不適用）。

## 忘了 export 之後怎麼救

agent 連續三次一起來就退出，表上會變成 `stopped`（原因欄只寫 `RunFailed … not restarting again`，代號要看它的 `stderr.txt`）。補上 export、shutdown 根再起之後，它**不會自己醒**，要再下一次 `aos-agent -d _stack ctl start <名>`；起來後先前排隊的問題會照樣答。
