# proto8/archive — 封存索引

封存的東西放這裡，只作歷史保留，不測試、不維護內部連結。只准追加列。

| 名稱 | 封存日期 | 原因 |
|------|---------|------|
| [topdown/](topdown/README.md) | 2026-11-03 | 原 `proto8/topdown/`（10-25 galtxt 由上而下兩隊：甲隊 galtxt-a、乙隊 galtxt-b）；trace.jsonl 拿掉後兩隊靠它量測的 7 個測試紅，使用者 11-03「封存 topdown」。測試 8 檔搬入 `topdown/tests/`、code map 兩檔搬入 `topdown/code-map/` |
| [llm-kernel-demo/](llm-kernel-demo/README.md) | 2026-11-03 | 原 `proto8/demo/llm-kernel`（一個 daemon 管 LLM kernel 與三隻 agent-ivy）；使用者 11-03 晚瘦身候選「可以先封存，等之後我們進展到那塊的時候可以拉出來看看」。demo/run.sh 那段拿掉、test_llm_kernel 的 demo 那案切到 `tests/`；aos-llm-kernel／aos-llm-send 本身沒動 |
| [self-improve/](self-improve/README.md) | 2026-11-03 | 原 `proto8/demo/self-improve`，連同只有它用的 `lib/aos/try_run`、`extras/sandbox/examples/self-improve.json`、test_self_improve.py 整檔、test_sandbox 的 SelfImproveSandboxTest；同上瘦身候選 |
| [nvim/](nvim/README.md) | 2026-11-03 | 原 `proto8/extras/editors/nvim`（aos_nvim 外掛）與 test_lua_aos 的 headless smoke；同上瘦身候選 |
| [agent-dan-langs/](agent-dan-langs/README.md) | 2026-11-03 | Lua／Janet 的 `agent_dan` 範例與三個 skip 中的測試案（demo/agent-dan 11-02 晚已刪）；同上瘦身候選 |
| [aos-chat/](aos-chat/README.md) | 2026-11-03 | 原 `proto8/extras/human/bin/aos-chat` 與 test_human 的 ChatTest；同上瘦身候選 |
