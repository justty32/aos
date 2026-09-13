# aos 遊樂場

給人玩的。五站，每站十分鐘內。所有東西都放在 repo 外面的 `~/aos-play/`，玩壞了整個資料夾刪掉重來，repo 不會髒。

## 開場（每次開新終端機都要做前兩步）

```sh
cd ~/repo/simple_tools/aos
source playground/env.sh      # 把指令放進 PATH、決定遊樂場和 daemon 的家在哪
playground/up.sh              # 上電（daemon）、開機（kernel，掛好 LLM 排程）、鋪五站的檔案
```

`up.sh` 最後會印一張 `aos-kernel ls` 的表：兩顆 cpu 都 idle、最後一行 `llm:` 是 LLM 排程的狀態。看到就成功了。重複跑沒關係，它每一步都會先看有沒有做過。

LM Studio 要開著、載一顆模型（`lms load google/gemma-4-e4b`）。沒開的話第 1、3、4、5 站會失敗，第 2 站照玩。

三個常用動作，隨時可用：

```sh
aos-kernel ls $K              # 誰在哪顆 cpu、跑了幾次、上次退出碼、在等嗎、LLM 排隊幾張
aos-daemon-ctl ls             # 硬體層：daemon 活著嗎、掛了哪些 inst
tail -f $K/kernel.log         # kernel 每回合的流水帳
```

## 第 1 站：問本機模型一句話（同步，不經 kernel）

```sh
cd $AOS_PLAY/stations/1-ask-once
aos-llm models endpoint.json                       # 列 LM Studio 載著的模型
aos-llm call endpoint.json request.json result.json
jq -r .text result.json                            # 只看回答
```

玩法：改 `request.json` 的問題再叫一次。五站的請求都沒設 `max_tokens`，因為 gemma-4 會先「想」一段（`usage.reasoning`，隨便一句話也想三四百字），想的字數也算在額度裡；設了小額度 `text` 就是空的、`finish_reason` 是 `length`。把 `endpoint.json` 的 `model` 故意打錯再叫，看它 4 毫秒就擋下來、不花 token（`error.kind` 是 `model_not_found`）。

## 第 2 站：逐步 JSON，等一個檔

程式是 `prog.json`，三格：記開始時間並宣告「要等 `go.txt`」→ 讀 `go.txt` 寫成 `got.txt` → 記結束時間。每叫一次只跑一格。

```sh
cd $AOS_PLAY/stations/2-json-wait
aos-step-json prog.json            # 第 0 格：寫 started.txt，開始等 go.txt
aos-step-json prog.json; echo $?   # 101 ＝ 在等，什麼都沒做
echo 開門 > go.txt
aos-step-json prog.json            # 檔到了：接著跑第 1 格
aos-step-json prog.json            # 第 2 格
aos-step-json prog.json; echo $?   # 100 ＝ 全部做完
aos-step-json prog.json --status   # 隨時看進度（pc、history、waiting）
```

再玩一次：`aos-step-json prog.json --reset && rm go.txt got.txt`，這次不用手叫，交給 kernel：

```sh
aos-kernel add $K inst.json --name json-wait
aos-kernel ls $K                   # 過一秒再看：CPU_STATE 是 waiting、WAIT 等了 N 回合
echo 開門 > go.txt                  # 下一回合它就自己跑完，被收進 done
```

## 第 3 站：逐步 Python 問 LLM（丟給 kernel 排隊）

`job.py` 三格：`ask` 把問題丟給 kernel 的 LLM 排程、宣告要等結果檔 → `read` 讀答案 → `save` 寫 `answer.txt`。

```sh
cd $AOS_PLAY/stations/3-py-llm
aos-kernel add $K inst.json --name py-llm
watch -n1 aos-kernel ls $K         # 看它 waiting → llm running → done（幾秒到十幾秒）
cat answer.txt
```

想手動一格一格走也行：`aos-step-py job.py`，等的時候會退 101。

玩法：改 `QUESTION`、`--reset`、再 `add` 一次——同一個名字同一個問題會直接拿回舊答案（不重花 token）；問題改了就會撞名，把 `job.py` 裡的 `"play-py-1"` 換個名字，或 `rm $K/llm/results/play-py-1.json`。

## 第 4 站：逐步 Lua，同步問 LLM ＋ 塞 binary

```sh
cd $AOS_PLAY/stations/4-lua-b64
aos-step-lua job.lua               # ask：同步問（這格會等模型回答）
aos-step-lua job.lua               # stash：塞一段不是文字的東西進 state
aos-step-lua job.lua               # write
cat job.state.json                 # blob 長成 {"$b64":"..."}（合法 UTF-8 的字串會存成普通字串，只有真的 binary 才包）
```

## 第 5 站：逐步 Lisp（Janet）

`prog.janet` 五個 form，一次跑一個；`def` 過的東西下一格還在（環境存成 image）。

```sh
cd $AOS_PLAY/stations/5-lisp
aos-step prog.janet                # 連叫五次，第四次開始等結果檔（退 101）
aos-step prog.janet --status
jq -r .text answer.json
```

或直接 `aos-kernel add $K inst.json --name lisp` 交給 kernel。

## 故意弄壞

- 排一個永遠等不到檔的行程（第 2 站不寫 `go.txt`）：`ls` 標 `waiting`；再排別的進來，它會讓出 cpu。
- 讓 Python 某格丟例外：訊息會說第幾格、哪個函式、第幾行，全文在 `job.py.error`；連續失敗 10 次 kernel 把它丟進 `$K/procs/bad/`。
- 跑到一半改程式（插一格）：它會警告格數對不上，但照跑；想乾淨重來就 `--reset`。
- 停掉 daemon（`playground/down.sh`）再丟 LLM 單：會說「沒送出去，已撤單」。

## 收工與重來

```sh
playground/down.sh      # 停 daemon，檔案都留著，下次 up.sh 接著玩
playground/reset.sh     # 整個 ~/aos-play 刪掉，從零開始
aos-kernel rm $K NAME   # 只拿掉一個行程
```

## 想看更多

- 作業系統那層（daemon／kernel／inst.json）：[proto4-3/README.md](../proto4-3/README.md)
- LLM 兩層：[proto4-5/README.md](../proto4-5/README.md)
- 逐步 JSON／Python／Lua：[proto4-6/README.md](../proto4-6/README.md)；逐步 Lisp：[proto4-4/README.md](../proto4-4/README.md)
- 別人怎麼玩的：[proto4/notes/play/](../proto4/notes/play/README.md) 有四輪試玩報告
