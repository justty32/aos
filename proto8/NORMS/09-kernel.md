← [回入口 NORMS.md](../NORMS.md)｜主題：**kernel**｜概念：[CONCEPTS kernel](../CONCEPTS/04-kernel.md)（C-47 定義；C-09～C-15、C-28、C-29、C-38）｜規範：本檔（打包 N-03 在[時空](02-設計理念-時空.md)；`_metainfo` 在[待定](08-待定.md)）｜實作：現無實作（舊的兩支在 git 歷史 5546be29，10-19 刪；照「資料夾＝程式」重寫時再對；規劃見 [thinking 通用 kernel](../thinking/2026-10-15-general-kernel.md)）

# kernel 規範

- **N-42**（10-15 定，草稿）先做兩種 kernel，都基於 daemon：(1) 管 LLM 呼叫的 kernel；(2) 通用管理的 kernel（以 agent 作判斷）。具體機制再規劃（[thinking 10-15 kernel 截流](../thinking/2026-10-15-kernel-intercept.md)有閘門／信箱草案；六題未決 10-15 使用者「隨意」、照建議預設定案，見 [LLM kernel](../thinking/2026-10-15-llm-kernel.md)）。兩種現在都無實作（10-19 刪舊版進 git，待照新做法重寫）。出自 C-47。**10-16 維持兩支**：KISS 重審曾推薦「兩支併成一支、沒寫判官＝管 LLM 的那種」，使用者：「兩隻kernel不併成一支。」（[KISS 重審拍板 5](../thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)），彙整 5.1 撤回。
