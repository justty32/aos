← [回入口 NORMS.md](../NORMS.md)｜主題：**kernel**｜概念：[CONCEPTS kernel](../CONCEPTS/04-kernel.md)（C-47 定義；C-09～C-15、C-28、C-29、C-38）｜規範：本檔（打包 N-03 在[時空](02-設計理念-時空.md)；`_metainfo` 在[待定](08-待定.md)）｜實作：第一種（管 LLM 呼叫）的基礎實作在 [lib kernel_llm.md](../lib/kernel_llm.md)（閘門 `aos_gate.py`＋身體 `aos_kernel_llm.py`，10-15）；第二種（通用管理）的基礎實作在 [lib kernel_general.md](../lib/kernel_general.md)（身體 `aos_kernel_general.py`＋判官 inst，10-15；規劃見 [thinking 通用 kernel](../thinking/2026-10-15-general-kernel.md)）

# kernel 規範

- **N-42**（10-15 定，草稿）先做兩種 kernel，都基於 daemon：(1) 管 LLM 呼叫的 kernel；(2) 通用管理的 kernel（以 agent 作判斷）。具體機制再規劃（[thinking 10-15 kernel 截流](../thinking/2026-10-15-kernel-intercept.md)有閘門／信箱草案；六題未決 10-15 使用者「隨意」、照建議預設定案，見 [LLM kernel](../thinking/2026-10-15-llm-kernel.md)）。兩種都有基礎實作：[lib kernel_llm.md](../lib/kernel_llm.md)、[lib kernel_general.md](../lib/kernel_general.md)。出自 C-47。
