← [aos-llm](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| llm cpu | kernel 裡池標 `llm`（或 agent 的 `info.llm.pool`）的一顆普通 exec cpu；它的 `envs` 放 PATH、金鑰、`AOS_LLM_CONFIG` |
| llm.json | 模型表：代號 → endpoint、真名、金鑰、HTTP 逾時。住在 llm cpu 那邊，agent 家裡沒有 |
| 代號 | agent `info.llm.model` 寫的名字（例如 `small`），在 llm.json 的 `models` 裡查真名 |

# 1. 用法與環境

```
aos-llm call [AGENT_DIR]    # （09-24 fix-r4 改）舊的 aos-llm-call 拿掉；之後 llm 相關的子命令都掛在 aos-llm 底下
aos-llm -h ／ aos-llm call -h
```

`AGENT_DIR` 留空＝`.`（目前資料夾）；必須是 agent 家（[agent.md §1](../agent/layout.md)）。沒有別的旗標。裸 `aos-llm`（沒子命令）＝用法錯 2（09-24 fix-r4 補）。

要的環境（都由那顆 llm cpu 給：[kernel §1.1](../kernel/info.md) 的 `info.pools.<P>.envs` 寫進池的 `envs.json`，池裡每顆 cpu 的 inst 都引用它）：

| 變數 | 用途 | 沒有時 |
|---|---|---|
| `AOS_LLM_CONFIG` | llm.json 的**絕對路徑** | 沒設、空字串、不是絕對路徑＝`ConfigInvalid`，退 1 |
| `PATH` | 找得到 `aos-llm` 本身（工作 inst 的 `argv` 寫 `["aos-llm", "call", <agent 家>]`） | 那件工作是 exit 127 |
| 金鑰變數 | llm.json 裡 `$env` 讀的 | `EnvironmentVariableMissing`，退 1 |

K 的 info 例子（`pools` 裡的一格）：

```json
"llm": {"count": 1,
        "envs": {"PATH": {"$fmt": {"$val": "/abs/proto5/cli:${p}", "p": {"$env": "PATH"}}},
                 "AOS_LLM_CONFIG": "/abs/llm-home/llm.json",
                 "LMSTUDIO_KEY": {"$env": "LMSTUDIO_KEY"}}}
```

改池的 `envs`（改 info，kernel 下一格重寫 `K/pools/<P>/envs.json`），之後（重）拉的 cpu 生效；要讓活著的立刻換，用 `aos-daemon kill --pool <dpool> --all`（[daemon §6.3](../daemon/cli.md)）。（2026-09-24 池式納入改）
llm.json 本身可以隨時改，下一次問就生效（每次跑都重讀）。

# 7. 給程式用

```python
body = aos_llm_call.build_request(agent_dir, config)   # 只組、不打；config 是讀驗好的 llm.json
msg  = aos_llm_call.call(agent_dir)                    # 讀 AOS_LLM_CONFIG、組、打、驗，回 message dict；失敗丟帶 code／msg 的例外
```
