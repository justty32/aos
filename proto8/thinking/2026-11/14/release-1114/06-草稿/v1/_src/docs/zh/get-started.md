# 開始用：不用任何模型，跑起第一棵樹

**一句話**：建好程式、起兩個資料夾、掛一隻叫 ann 的 agent、跟它說一句話——然後打開資料夾，看它剛剛做了什麼。全程不用模型帳號；aos 除了 `~/aos` 和 `~/aos-demo` 兩個資料夾，不寫你家目錄的任何地方（建置時 vcpkg 會在 `~/.cache/vcpkg` 放下載快取）。

<!-- copy:TRY --> 這頁走的是 L0：用「假腦」代替模型。假腦會照固定格式回話，但它走的路跟真腦一模一樣：收信、叫工具、寫紀錄、回信。

<!-- source: this page's bash blocks were run literally (bin/run-doc.py), 11-14: clone from a local mirror, HOME = an empty folder, build + steps 2-7, then a second round in ~/aos-demo2; both passed, no process left; HOME afterwards held only aos/, aos-demo/, aos-demo2/ and .cache/vcpkg. Output: drafts/ref/get-started.out.txt -->


開始前：Linux（或 WSL2）、`git`、`bash`、Python 3.11 以上、CMake 3.21 以上、支援 C++20 的編譯器、[vcpkg](https://vcpkg.io)。細節看[需求](install/requirements.md)。請開一個**新的 bash**，裡面不要有舊的 `AOS_*` 變數。

> agent 會用你的帳號執行程式。第一次玩，建議在拋棄式帳號或容器裡試——見[安全說明](manual/security.md)。

## 1. 抓原始碼、建置

```bash
git clone <REPO_URL> ~/aos
cd ~/aos/proto8/impls && cmake -B build && cmake --build build -j
```

建置會用 vcpkg 抓 C++ 需要的 JSON 函式庫。vcpkg 裝在 `~/dev/vcpkg` 就什麼都不用設；裝在別處就先 `export VCPKG_ROOT=<vcpkg 的位置>`。

<details>
<summary>不想用 vcpkg？（待驗）</summary>

沒給 vcpkg 時，CMake 會改找系統裝的 nlohmann-json。這條路我們還沒在乾淨環境實測過，裝了發行版的 `nlohmann-json` 套件理論上就能建。卡住請看[疑難排解](manual/troubleshooting.md)。

</details>

## 2. 讓這個殼找得到指令

```bash
export AOS_HOME=~/aos/proto8
export PATH=$(ls -d $AOS_HOME/impls/*/bin $AOS_HOME/cmd/*/bin | tr '\n' ':')$PATH
export PYTHONPATH=$AOS_HOME/py:$AOS_HOME/lib
```

只改這個殼，關掉就沒了。想長期裝，看[安裝](install/index.md)的 `install.sh`。

## 3. 起兩個資料夾：腦，和你的樹

```bash
mkdir -p ~/aos-demo/llms ~/aos-demo/tree

cd ~/aos-demo/llms
cp -r $AOS_HOME/kernel/llm-kernel def
nohup aos-exec --stack stacks/llm def > llm.log 2>&1 &

cd ~/aos-demo/tree
cp -r $AOS_HOME/templates/daemon-root defs
cp -r $AOS_HOME/templates/agent-fsm defs/ann
nohup aos-exec --stack stacks/root defs > root.log 2>&1 &
```

```text
~/aos-demo/
  llms/   def/ 是 llm kernel 的定義，stacks/llm/ 是它跑起來的狀態（這裡是假腦）
  tree/   defs/ 是樹的定義，defs/ann/ 是 agent 的定義，stacks/root/ 是樹跑起來的狀態
```

`def` 和 `defs` 是**定義**（像程式碼），`stacks/` 是**跑起來之後的一切**（像記憶體）。兩個並排放，樹就會自己找到旁邊的腦。

## 4. 掛上 ann，先看一眼它的資料夾

```bash
aos-agent -d stacks/root ctl add -w . defs/ann
aos-daemon-ctl -d stacks/root ls
ls stacks/root/procs/ann/
```

```text
ann	running	1293838	-	~/aos-demo/tree	-
# daemon: running (pid 1293334)

hooks  queue  stage.txt  state_flux.json  state.json  stderr.txt
```

ann 現在是一個在跑的行程，而它的一切都在 `stacks/root/procs/ann/` 這個資料夾裡。還沒有對話紀錄。

<details>
<summary>表上另外兩行 _clock、_sweeper 是什麼</summary>

樹自帶的兩個小幫手：`_clock` 數拍子，`_sweeper` 收拾停掉的行程。它們也是 proc，跟 ann 一樣在 `procs/` 底下有自己的資料夾。

</details>

## 5. 跟 ann 說一句話

```bash
aos-agent -d stacks/root -t ann say "hello, who are you?"
timeout 60 aos-agent -d stacks/root -t ann listen
```

```text
FAKE ANSWER to: hello, who are you? (tool said: 2026-11-14T04:33:40Z)
```

假腦的回答很呆，但看括號：它**先叫了一個工具**（問現在幾點），才回話。

## 6. 再看一次資料夾

```bash
ls stacks/root/procs/ann/
tail -n 3 stacks/root/procs/ann/history.jsonl
```

```text
history.jsonl  hooks  interfaces.json  observed.jsonl  queue  stage.txt  state_flux.json  state.json  stderr.txt  think

{"role": "assistant", "content": null, "tool_calls": [{"id": "call_fake_2", "type": "function", "function": {"name": "peek_now_time", "arguments": "{}"}}]}
{"role": "tool", "tool_call_id": "call_fake_2", "content": "2026-11-14T04:33:40Z\n"}
{"role": "assistant", "content": "FAKE ANSWER to: hello, who are you? (tool said: 2026-11-14T04:33:40Z)"}
```

跟第 4 步比，多了 `history.jsonl`（整段對話）和 `think/`（它想的過程）。最後三行就是剛才那一來一回：**叫工具 → 工具回答 → 最後的答案**。沒有藏起來的狀態——想知道 agent 在做什麼，打開資料夾就好。

## 7. 停掉，確認都停了

```bash
aos-daemon-ctl -d ~/aos-demo/tree/stacks/root shutdown
aos-daemon-ctl -d ~/aos-demo/llms/stacks/llm shutdown
aos-daemon-ctl -d ~/aos-demo/tree/stacks/root ls
```

```text
daemon at ~/aos-demo/tree/stacks/root stopped (ctl seq 1); 3 procs asleep, they wake when it starts again
daemon at ~/aos-demo/llms/stacks/llm stopped (ctl seq 1); 1 procs asleep, they wake when it starts again
...
# daemon: not running (pid 1293334 is gone); the table above is what it left
```

看到 `not running` 就是停乾淨了。ann 只是「睡著」：資料夾都還在，下次起樹它會接著醒來。

想從頭再玩一次：先照上面停掉，再換一個新的示範夾（例如 `~/aos-demo2`）從第 3 步開始。

## 下一步

- [第一棵樹，慢慢看](tutorials/01-first-tree.md)：每個資料夾各是什麼、再加第二隻 agent
- [安裝](install/index.md)：長期裝、四個等級（假腦 → 真模型 → Claude Code → 沙箱）
- 卡住了：[疑難排解](manual/troubleshooting.md)
