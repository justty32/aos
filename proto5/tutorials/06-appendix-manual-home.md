← [教程索引](README.md)｜接在 [03 第一個 agent](03-first-agent.md) 之後讀

# 06 附錄：不用 init，手寫一個 agent 家

**目標**：看清楚 agent 家其實就是一個資料夾加三份檔；`init` 只是替你寫好它們。

**前提**：kernel 開著（[01](01-daemon-kernel.md)）。新終端先 `. $HOME/aos-try/env.sh`。

## 1. 寫三份檔

```sh
mkdir -p $W/amy/prompts $W/amy/tools
cat > $W/amy/info.json <<'EOF'
{"_metainfo": {"_type": "llm_agent", "_version": 1},
 "llm": {"model": "default", "timeout_ms": 190000},
 "tools": ["tools/base.json"],
 "tick": {"interval_ms": 500}}
EOF
cat > $W/amy/prompts/system.json <<'EOF'
{"content": "你是繁體中文助理。要知道現在時間就呼叫 date 工具，拿到結果後用一句話回答。"}
EOF
cat > $W/amy/tools/base.json <<'EOF'
[{"type": "function",
  "function": {"name": "date", "description": "取得現在的本機日期與時間",
               "parameters": {"type": "object", "properties": {}}},
  "_meta": {"argv": ["date", "+%Y-%m-%d %H:%M:%S"]}}]
EOF
aos-agent check --target $W/amy
```

最後一行 `設定檢查通過；未測模型連線（--probe 會測）` 就對了（中間各行跟 [03 第 2 步](03-first-agent.md#2-檢查)一樣）。
`info.json` 沒寫的都有預設：人格 `prompts/system.json`、記憶 `prompts/history.json`、問模型派 `llm` 池、工具與走格派 `default` 池。

## 2. 登記、投話、看回話

手寫的家沒有 `input/` 資料夾，輸入投到 `input.json`。要**原子地**投：先寫暫存檔再 `mv`，免得它讀到寫一半的檔。

```sh
aos-agent start --target $W/amy
echo '"現在幾點？請用工具查。"' > $W/amy/input.tmp && mv $W/amy/input.tmp $W/amy/input.json
sleep 20
aos-agent listen --target $W/amy --last
```

`start` 印 `started agent-amy`；`listen` 印一句報時。收過的輸入搬進 `amy/done/`（`init` 的家是 `input/done/`）。
`aos-agent say` 在這種家也能用，一樣投到 `input.json`。

## 3. 收工

```sh
aos-agent stop --target $W/amy
```

## 底下在幹嘛

`info.json` 各格、`input` 可以指到哪、記憶的格式，見 [agent 家的「使用者只需要懂的」](../spec/agent/essentials.md) 與 [info.json](../spec/agent/info.md)、[state.json 的 input](../spec/agent/state.md)。
