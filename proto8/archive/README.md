# proto8/archive — 封存索引

封存的東西放這裡，只作歷史保留，不測試、不維護內部連結。只准追加列。

| 名稱 | 封存日期 | 原因 |
|------|---------|------|
| [llm-kernel-demo/](llm-kernel-demo/README.md) | 2026-11-03 | 原 `proto8/demo/llm-kernel`（一個 daemon 管 LLM kernel 與三隻 agent-ivy）；使用者 11-03 晚瘦身候選「可以先封存，等之後我們進展到那塊的時候可以拉出來看看」。demo/run.sh 那段拿掉、test_llm_kernel 的 demo 那案切到 `tests/`；aos-llm-kernel／aos-llm-send 本身沒動 |
| [self-improve/](self-improve/README.md) | 2026-11-03 | 原 `proto8/demo/self-improve`，連同只有它用的 `lib/aos/try_run`、`extras/sandbox/examples/self-improve.json`、test_self_improve.py 整檔、test_sandbox 的 SelfImproveSandboxTest；同上瘦身候選 |
| [nvim/](nvim/README.md) | 2026-11-03 | 原 `proto8/extras/editors/nvim`（aos_nvim 外掛）與 test_lua_aos 的 headless smoke；同上瘦身候選 |
| [agent-dan-langs/](agent-dan-langs/README.md) | 2026-11-03 | Lua／Janet 的 `agent_dan` 範例與三個 skip 中的測試案（demo/agent-dan 11-02 晚已刪）；同上瘦身候選 |
| [aos-chat/](aos-chat/README.md) | 2026-11-03 | 原 `proto8/extras/human/bin/aos-chat` 與 test_human 的 ChatTest；同上瘦身候選 |
| [agent-round-concepts/](agent-round-concepts/README.md) | 2026-11-03 | **程式刪除、只留概念**：round 那套用格組起來的 agent（`lib/agent/round`、parts、queue／history／act／compact、`lib/endpoint`、`lib/aos/ask_round`、`demo/agent-nia`）與 aos-ai（`extras/ai_tools/bin/aos-ai`、`aos_ai_*.py`、lib/aos 六個工具、Claude skill）；使用者 11-03 晚「該刪的都刪光刪乾淨」「一起刪……只需要留下他們的概念就好」。aos-mcp、aos_ws、aos-say／listen 留著 |
| [send-message-memory/](send-message-memory/README.md) | 2026-11-04 | 原 `proto8/lib/aos/send_message`（`AOS_ROSTER`）與 `proto8/lib/aos/memory`（`AOS_HEAP`）；主人 demo/talk、agent-kai 都不在了、環境變數不合 N-63；使用者 11-04 晚「封存」。`check_inbox` 留著 |
| [resident-bob/](resident-bob/README.md) | 2026-11-04 | 原 `proto8/thinking/2026-11/02/resident-bob/`（常駐版 bob：一個 exec＋一個 loop 掛在 daemon 底下）；使用者 11-03「B5.封存吧，eca是他的全面強化版，真的沒必要了。」、11-04 晚「封存」。整份 AI 產出的 03、07、08、09、11、12、13 同晚先刪 |
