← [教學入口](README.md)｜上一章 [02 架 daemon](02-架daemon.md)｜下一章 [04 寫一份原始碼](04-寫原始碼.md)

# 03 灌 kernel（用現有的 kernel 定義，掛個 proc 上去）

**結論**：抄一份 llm kernel 的範本到 `llm/`，`aos-daemon-ctl add` 把它掛上板子，它就成了表上的一列；先用出廠預設的**假腦**（不連網、不花錢，固定回 `FAKE ANSWER to: …`）確認它會答。

llm kernel 像一台專門打電話的總機：agent 要想事情，就寄一封信進總機的收件匣，總機去問模型、把答案寄回來。它自己也是一台小 daemon（有自己的表），掛在板子上。

「初始 kernel」由三塊組成（使用者 11-20：「兩件+最小核心。然後弄一串可選的…」）：

- **最小核心**：板子買來就有——上一章的 daemon、時鐘 `_clock`、清道夫 `_sweeper`，加上信箱與「我是誰」。
- **llm 件**：這一章灌的 llm kernel。名義上可選，但 agent 沒有它就不能想（第一次問腦就 `LlmKernelMissing` 停下）；不會想的 proc 才用不到。
- **權限件**：一台站，管「准不准開 proc、同時幾個」。可選、預設不開，這份教學不裝；[start-api](../../templates/starts/start-api/README.md#選裝權限件預設不開) 帶一份沒掛的，要的話照那裡三步打開。它是給守規矩的人用的規矩，不是牆：真要擋，靠換 Linux 帳號。

另外還有「一串可選件」，有哪些還沒定。每塊的細節在 [kernel 入口「初始 kernel」](../../templates/kernels/README.md#初始-kernel買了板子之後灌什麼)。

## 掛上去（視窗 B，板子要開著）

```sh
cp -r $AOS_HOME/templates/kernels/llm-kernel llm
ls llm
aos-daemon-ctl -d .stack add --auto-restart llm
aos-daemon-ctl -d .stack ls
aos-daemon-ctl -d .stack/procs/llm ls
```

你會看到：

```
_entry
daemon.json
endpoints
fake_slow
interfaces.json
kernel.json
kernel_hookeds.json
kernel_hooks.json
01795071378424737732.803235.2492535
_clock	running	803030	-	-	-
_sweeper	running	803031	-	-	-
llm	running	803252	-	-	-
# daemon: running (pid 803028)
# root daemon (no supervisor)
_sweeper	running	803253	-	-	-
# daemon: running (pid 803252)
# supervisor ~/code/aos-tut/.stack/: running
```

- `add` 印的那串數字是「掛上去」這封請求信的名字，看到就是送出了。
- 表上多了 `llm`；它跑起來的樣子在 `.stack/procs/llm/`，正好是上一章 `.env` 指的地方。
- `--auto-restart`＝它掉了板子會自己再起它。
- 第二張表是 kernel 自己的表，最後一行說它歸板子管。

## 確認它會答

```sh
export AOS_LLM_KERNEL=$PWD/.stack/procs/llm
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask
aos-llm ls | head -4
```

```
{"role": "assistant", "content": "FAKE ANSWER to: hi"}
astra	normal	high	272000	-	-	LiteLLM gpt-6 astra: images and creative work, about 3x sol's price
fake	fast	free	-	-	-	fake brain: calls peek_now_time (or the first tool), then answers FAKE ANSWER to ...
fake-demo-fast	fast	free	-	1	-	fake brain that takes 3 s, one at a time, sorted first (templates/kernels/docs/03 part 3)
fake-demo-self	fast	free	-	-	-	scripted fake brain for templates/kernels/docs/03 part 1: adds math to its own tools, then uses it
```

`aos-llm ls` 列的是 llm kernel 登記的**腦包**（一個代號＝一組模型設定，例如 `fake`、`luna`；照名字排，前面幾個真模型的包也列出來，這章用不到）；agent 只寫代號，不寫網址和模型名。預設代號是 `fake`。`export AOS_LLM_KERNEL` 只是為了在這個視窗直接問；板子上的 agent 從 `.env` 繼承，不用你設。

<details><summary>另一種擺法：kernel 自己一台、不掛在板子上</summary>

主線是掛在板子上（使用者 11-20「掛同一塊板子」；`templates/starts/start-api` 也這樣擺）。另一種是 kernel 自己一台：另開一個視窗 `aos-exec --stack <它的 stack> llm` 自己起停，`.env` 的 `AOS_LLM_KERNEL` 指那個 stack。這樣關板子時 kernel 不跟著關，好幾塊板子可以共用一台 llm daemon；代價是要多管一台的起停，第 08 章的一句全關也就不夠了。
</details>
