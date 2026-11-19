# proto8 討論紀錄：2026-11-19

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [公司WSL-環境-1119](公司WSL-環境-1119.md) | 公司 WSL 的 aos 程式裝到 repo 這層（install.py 退 0、28 支、暫存樹假腦過）；LiteLLM 查清兩台版本（家機 1.87.5、公司昨天裝的 1.109.1 還在但登入沒走完），沒起，版本待使用者拍板 |
| [aos-compile-庚](aos-compile-庚/README.md) | 庚的設計稿：一支 `agent.py` 宣告 SYSTEM／TOOLS／LLM／FSM 重生定義夾的 json；打架規則定成「`agent.py` 永遠贏、記指紋分過時與被手改、`agent_def check` 重生而 `defs check` 只報」；五刀範圍（第一刀只加 lib 與骨架）；六題待使用者拍板，沒改程式 |
| [litellm-1.109.1-實測](litellm-1.109.1-實測.md) | 公司 WSL 的 ~/litellm-proxy（1.109.1）起起來留著跑；三個 ChatGPT 模型非串流與串流都 200 回 ok、aos 整條線用 luna 回真字；登入是抄 codex 的同一份 token（續期時一邊會被登出）；附進 repo 的盤點，推薦併進 llm_proxy 當子夾，待使用者裁 |
