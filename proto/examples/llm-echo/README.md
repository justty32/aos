# llm-echo

跑這個會看到父地投一筆請求給 LLM 世界，LLM 世界用假後端（`echo:`，不打真的網路）把 prompt 原樣回話，父地 `await` 到回話再印出來。

## 怎麼跑

```sh
proto/examples/llm-echo/run.sh
```

或手動一步一步來（記得先設 `AOS_HOME` 指到暫存目錄，不要污染 `~`）：

```sh
cd proto/examples/llm-echo
export AOS_HOME="$(mktemp -d)"
python3 ../../aos.py init .
python3 ../../aos.py llm init          # 建 LLM 世界，預設處理單元 endpoint:"echo:"
echo '哈囉' > prompt.txt
python3 ../../aos.py deliver "$AOS_HOME/.aos/llm" \
  '{"kind":"llm","prompt":"prompt.txt","result":"answer.txt","tier":"fast"}' \
  --sender "$(pwd)"
python3 ../../aos.py exec .            # 第 0 格：wait 這步還沒等到，HOLD
python3 ../../aos.py llm tick --land "$AOS_HOME/.aos/llm"   # LLM 世界處理這筆請求，寫 answer.txt
python3 ../../aos.py exec .            # 第 1 格：wait 等到了，推到 print
python3 ../../aos.py exec .            # 第 2 格：print，印出 answer.txt
```

## 這個範例在示範什麼

- LLM 世界是**另一塊獨立的地**（`$AOS_HOME/.aos/llm`），別的地要用 LLM 就投一筆 `kind:"llm"` 的投遞物給它，不是為每次請求開一塊地。
- `result` 一樣是**父指定的結果落點**（`answer.txt`）；相對路徑以投遞者（`--sender` 指的那塊地）為準。
- 假後端 `endpoint:"echo:"`：不打任何網路，把 prompt 原樣回，前面加一行 `echo:<單元名>` 當標記，回話原文直接寫進 `result`。**測試與範例一律用這個假後端。**
- 要換真後端：改 `$AOS_HOME/.aos/config.json` 的 `units`，把 `endpoint` 換成 `http://localhost:1234/v1`（LM Studio），填 `model`，`aos llm tick` 就會真的打過去——但這個範例的 `run.sh` 絕對不做這件事。
- 帳簿 `$AOS_HOME/.aos/ledger.jsonl` 每次呼叫記一行：誰叫的、用了哪個單元、花了多久。
