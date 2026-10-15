← [回入口 NORMS.md](../NORMS.md)｜主題：**kernel**｜概念：[CONCEPTS kernel](../CONCEPTS/04-kernel.md)（C-47 定義；C-09～C-15、C-28、C-29、C-38）｜規範：本檔（打包 N-03 在[時空](02-設計理念-時空.md)；`_metainfo` 在[待定](08-待定.md)）｜實作：第一種（管 LLM 呼叫）的基礎實作在 [lib kernel.md](../lib/kernel.md)（閘門 `aos_gate.py`＋身體 `aos_gate_kernel.py`，10-15）；第二種尚無（討論在 [thinking 10-15 kernel 截流](../thinking/2026-10-15-kernel-intercept.md)、[LLM kernel](../thinking/2026-10-15-llm-kernel.md)）

# kernel 規範

- **N-42**（10-15 定，草稿）先做兩種 kernel，都基於 daemon：(1) 管 LLM 呼叫的 kernel；(2) 通用管理的 kernel（以 agent 作判斷）。具體機制再規劃（[thinking 10-15 kernel 截流](../thinking/2026-10-15-kernel-intercept.md)有閘門／信箱草案；六題未決 10-15 使用者「隨意」、照建議預設定案，見 [LLM kernel](../thinking/2026-10-15-llm-kernel.md)）。第一種已有基礎實作：[lib kernel.md](../lib/kernel.md)。出自 C-47。
