← [教程索引](README.md)｜上一篇 [03 第一個 agent](03-first-agent.md)｜下一篇 [05 管一大堆 agent](05-many-agents.md)

# 04 給 agent 加工具、暫停它、救回它

**目標**：自己寫一支工具給 bob 用；看工具壞了會怎樣；手動暫停與解除；模型端點壞了它會自己暫停，修好後怎麼救。

**前提**：做完 [03](03-first-agent.md) 第 1～3 步，kernel 開著、bob 的家在。先確定 bob 登記著（03 最後 stop 過也沒關係；還登記著的會印 `already started agent-bob`、退 0）：

```sh
. $HOME/aos-try/env.sh
aos-agent start --target $W/bob
```

## 1. 寫一支工具

工具就是一支程式：**stdin 收模型給的參數（一個 JSON）、stdout 印的東西原樣交給模型**。先寫程式、手動試一次：

```sh
mkdir -p $W/bob/tools/bin
cat > $W/bob/tools/bin/add <<'EOF'
#!/usr/bin/env python3
import json, sys
args = json.load(sys.stdin)
print(args["a"] + args["b"])
EOF
chmod +x $W/bob/tools/bin/add
echo '{"a": 2, "b": 3}' | $W/bob/tools/bin/add
```

印 `5` 就對了。

## 2. 告訴 agent 有這支工具

一份工具檔＝一個 OpenAI `tools` 陣列，每個元素多一格 `_meta` 說要跑什麼：

```sh
cat > $W/bob/tools/add.json <<'EOF'
[{"type": "function",
  "function": {"name": "add", "description": "把兩個整數加起來",
               "parameters": {"type": "object",
                              "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                              "required": ["a", "b"]}},
  "_meta": {"argv": ["tools/bin/add"]}}]
EOF
aos-agent check --target $W/bob
aos-agent say "請用 add 工具算 1234 加 4321，只回數字。" --target $W/bob --wait
```

`check` 會多一行 `ok   agent/tool/add: 可執行 tools/bin/add`。`say --wait` 約 15 秒印 `5555`。**不用重新 start**：放進 `tools/` 下一格就生效。

- `argv[0]` 含 `/`＝**相對 agent 家**的路徑，要有執行位；不含 `/`（像 `date`）就照 cpu 的 PATH 找。
- 工具跑的時候目前資料夾是 agent 家；最多跑 60 秒（`_meta` 裡寫 `"_timeout_ms"` 可改）。

## 3. 工具壞了會怎樣

```sh
chmod -x $W/bob/tools/bin/add
aos-agent check --target $W/bob
aos-agent say "請用 add 工具算 1 加 1。" --target $W/bob --wait 90
chmod +x $W/bob/tools/bin/add
```

`check` 那行變 `bad`，最後一行也跟著變：

```text
bad  agent/tool/add: 找不到可執行的 tools/bin/add；請修正工具路徑、執行權限或 PATH
ok   agent/tool/date: 可執行 date
有 bad，照上面的提示修好再 aos-agent start
```

（它已經登記著，修好就生效，不用真的重 start。）
agent 照樣會回話，模型看得到失敗原因，例如：「工具 add 執行失敗（exit 126，無法執行）…」。

工具失敗是**給模型看的結果**，不算 agent 自己的錯：`log/agent.err` 不會有這一行，`status` 也照樣 `ok`。
要看工具到底回了什麼，看記憶裡那則 `tool` 訊息：

```sh
python3 -c "import json; [print(m['role'], str(m.get('content'))[:120]) for m in json.load(open('$W/bob/prompts/history.json'))[-3:]]"
```

## 4. 手動暫停與解除

```sh
aos-agent pause --target $W/bob
aos-agent say "你好" --target $W/bob
aos-agent status --target $W/bob | head -1
aos-agent continue --target $W/bob
aos-agent listen --target $W/bob --wait 60
```

你會看到：`pause` 印 `paused …（aos-agent continue --target … 解除）`；暫停中 `say` 照收，但 stderr 警告「已暫停，continue 後才會處理」；
`status` 第一行 `health 手動暫停（aos-agent continue …）`；`continue` 印 `continued: 解除手動暫停`；然後回話出來。

暫停＝還登記在 kernel、每格照樣被叫，但什麼都不做。暫停中說的好幾句，continue 後會合成一輪一起回。

## 5. 模型端點壞了：連敗暫停

故意把 `llm.json` 的 port 改壞（這會影響**所有** agent，因為 `llm.json` 是共用的）：

```sh
sed -i 's/4000/4999/' $W/llm.json
aos-agent say "1 加 1 等於多少？" --target $W/bob --wait 120
aos-agent status --target $W/bob
```

問模型連續失敗 3 次它就停手（約 15 秒）。`say --wait` 退 101，`status` 會說：

```text
health 連敗暫停（aos-agent continue --target /home/you/aos-try/bob）
state  think  連敗暫停中（已連敗 3 次）
error  aos-llm call exit 1，看 …/bob/log/llm.err：aos-llm: EngineFailed: HTTP 請求失敗：[Errno 111] Connection refused（endpoint http://localhost:4999/v1，模型 default→deepseek-chat）
       已連敗 3 次，等 aos-agent continue --target …/bob
```

失敗 1、2 次時第一行是 `重試中（連敗 N/3）`，它還會自己再試。修好再解除：

```sh
sed -i 's/4999/4000/' $W/llm.json
aos-kernel check --probe | tail -1
aos-agent continue --target $W/bob
aos-agent listen --target $W/bob --wait 60
aos-agent status --target $W/bob | head -1
```

`continue` 印「已解除暫停，等下一次成功」；這時 `health` 也是這句。回話出來後才變回 `health ok`，舊錯另列一行、開頭標「（已恢復）」。
好幾個 agent 一起倒時，一次救全部用 `aos-agent continue --all`（[05](05-many-agents.md)）。

## 6. 想當 coding agent 用

不用自己寫工具：內建 `base` 工具包一次裝七支（read／write／edit／bash／grep／find／ls，仿 pi），裝了就能讀寫檔案、跑指令：

```sh
aos-agent tools add base --target $W/bob
```

在某個專案裡工作就加 `--root`（工具的路徑會關在這個資料夾裡，擋掉走出去）：

```sh
aos-agent tools add base --target $W/bob --root ~/proj
```

裝完不用重 `start`，下一格就生效。這時人格通常也要跟著換成 coding agent 那套（改 `$W/bob/prompts/system.json`），
不然模型不知道自己有這些工具能用。每支工具的參數、錯誤格式、工作根目錄怎麼算見 [proto5/tools/README.md](../tools/README.md)。

## 底下在幹嘛

- 模型要用工具時，agent 把每個工具呼叫寫成一份 inst，往 kernel `add --once` 到 `default` 池（`info.json` 的 `tool_pool`），下一格收結果、寫進記憶再問模型。（[工具檔格式](../spec/agent/info.md)、[act 怎麼跑工具](../spec/aos-agent/send.md)）
- `pause` 只是在家裡放一個 `paused` 檔；連敗暫停是家裡等一扇「門」（`continue-*.json`）打開。`continue` 把兩種都解開，
  再放一個 `resumed` 檔，下一次問模型成功才拿掉——所以才有「已解除，等下一次成功」這一段。（[暫停與解除](../spec/aos-agent/cli-status.md)、[連敗暫停](../spec/aos-agent/pause-clean.md)）
- 連敗只算**問模型**失敗；工具失敗交給模型自己判斷，不算。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `check` 說工具 `bad` | 路徑錯、沒執行位、或不含 `/` 的名字不在 cpu 的 PATH。照提示修，下一格生效 |
| 工具 JSON 寫壞，`aos-kernel ls` 行程表裡它的狀態是 `bad`、表下一行「agent-bob 壞了，看 …/log/agent.err」 | 設定讀驗錯連續失敗。照 `agent.err` 修好，`aos-agent stop` 再 `start` |
| 模型說「工具失敗 exit 127」 | 找不到程式：`#!` 那行、或 `argv[0]` 沒 `/` 又不在 PATH |
| `continue` 之後又連敗暫停 | 原因沒修好。先 `aos-kernel check --probe` 確認端點通 |

## 收工

`aos-agent stop --target $W/bob`；今天到此為止就照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關機。要接著做 [05](05-many-agents.md) 就先留著。
