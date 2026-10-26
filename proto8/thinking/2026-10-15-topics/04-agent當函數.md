← [回入口](../2026-10-15-topics.md)｜上一份：[03-試146-qwen與LM-Studio](03-試146-qwen與LM-Studio.md)

## 11. agent 當函數＋binding、當工具

**原文**（10-15，照記）：
- 「我會把 agent 的使用當作函數＋binding，表現形式就像：agent_call(system, history, engine, tools)，然後可以做 binding：agent_bob = {system:"...", history:"...", ...}, agent_bob.call(history, engine_args, tools_append)。具體體現在有一個 bob/ 資料夾，裡面存放相關東西，具體要使用的時候，可以把 cwd 指定到另一個地方，讓 history 等東西在另一個地方累積，而 bob/ 資料夾不變，這樣 bob 就是一個可重複使用的函數。」
- 「history 累積的地方，可以和實際的 cwd 不一樣，也就是 history 累積那塊，很像是函數本體的 stack。相對路徑那塊就是技術問題，概念我剛剛訂下了，規範我們慢慢來。」
- 「然後 tools 本身又是函數的一些包裝，對於 agent_bob.call 來說，更像是傳進去的，可以給他使用的函數。tools 中又可以包含其他 agent 的呼叫...」

**決定**
- 概念進 [C-46](../../docs/CONCEPTS/05-agent.md#agent函數binding)：定義（bob/，不變）、frame（history 等累積處，像 stack）、cwd 三處分開；tools＝傳進 call 的函數，bob 綁的只是預設，裡面可以是別的 agent。規範之後再說。
- agent 當工具：使用者「照預設做」。現行寫法見 [意見 1～4](../2026-10-15-opinions-1-4.md)（frame 由呼叫方決定、工具在 `work/<n>/` 跑）與 [inst-exec 第四版](../2026-10-15-inst-exec-v4.md)（工具 inst 的 argv 直接是 `aos loop`）；frame 現稱 stack（[agent-inherit § 四](../2026-10-16-agent-inherit.md#四使用者決定10-16)）。
