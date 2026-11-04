# 代理前置 token：要不要換

← [R1](README.md)｜數據：[evidence](evidence/proxy-overhead/README.md)

每次經 LiteLLM 打 chatgpt-*，都會多 1644 token：它塞了 Codex 的系統提示（1620）。aos 一單約 2606，這段占 63%。

**怎麼設**：在 `~/repo/llm_proxy` 停掉 proxy，改用
`CHATGPT_DEFAULT_INSTRUCTIONS='You are a helpful assistant. You have no tools; answer directly.' ./start_litellm.sh`
啟動。不能設成空字串，空的會退回原本的提示。

**省多少**：每次少約 1600 token。這題一單 2606 變約 1000（−62%）；大請求省的比例小一點。模型也不會再以為自己在 Codex 裡。

**風險**
- 後端可能不收非官方提示（回 4xx）。先打一次確認。
- astra 現在有 1408 token 吃快取，換了就沒了，但總量還是少很多。
- 整台 proxy 的 chatgpt-* 都會變。要靠 Codex 提示當寫程式代理的其他工具會受影響。

**怎麼驗證**：在 aos 根跑
`bash proto7-2/packs/llmcall/examples/litellm/run.sh /tmp/ef1-check`
看 `receipt.stdout.json` 的 prompt_tokens：從 1644 降到約 40 就對了。再跑一圈
`bash proto7-2/packs/author/examples/llm-request/run.sh chatgpt-gpt-6-sol /tmp/ef1-loop`
要過三關、close。

**怎麼還原**：停掉 proxy，不帶那個變數直接 `./start_litellm.sh`。

點頭的話，EF1 會再量一次 12 圈補前後表。
