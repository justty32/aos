# aos-eca — 外部 coding agent（claude／codex）的兩支指令

← [cmd](../README.md)｜範本：[templates/eca-claude](../../templates/docs/01-eca-claude.md)

- `bin/aos-eca-turn`：答一輪——從 stack 的 queue 認領一批、交給 CLI 就收信、回答接進 history。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)。
- `bin/aos-eca-screen`：eca 的 screen 子介面身體（open／close／watch），人經 `aos-agent` 叫。說明在 [cmd/docs/05](../docs/05-aos-llm與eca入口.md)。
