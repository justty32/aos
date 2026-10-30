# aos agent 慣例

← [proto8](../README.md)｜原話與拍板：[thinking/ideas](../thinking/2026-10-19-ideas.md)｜跟 proto8 原則相撞的七條，使用者已全部裁定：[ideas § 9](../thinking/2026-10-19-ideas.md)｜proto8 原則：[CONCEPTS](CONCEPTS.md)、[NORMS](NORMS.md)｜程式：[impls](../impls/README.md)（C++ 是唯一實作；aos-tick 例外，在 [bin](../bin/README.md)）、[demo](../demo/README.md)

**aos 本身只保證六個環境變數（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`；§ 19）和一支 `aos-exec`**（使用者 § 4；已升成規範 [N-57～N-62](NORMS/10-基礎設施-定義與工作區.md)）。其餘全是慣例：我們自己人寫 agent 時照抄的標準形狀，照抄的人不用想、看別人的 agent 一眼就懂（C-54）。**agent-bob 現在的樣子就是標準，stack 裡面自由**（拍板點 1）。

每條後面括號是依據：§ 幾＝[ideas](../thinking/2026-10-19-ideas.md) 裡使用者原話的段號；拍板點 1～3＝ideas § 8；C-xx／N-xx＝proto8 的概念與規範；引不到的、這份自己定的，標「本稿定」。

> **實作**：只有 C++ 的 [impls](../impls/README.md)（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 也是 C++、tick 先留 Python，`proto8/bin` 只剩 `aos-tick`）。impls 提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（loop／fsm 照 [ideas § 23](../thinking/2026-10-19-ideas.md)）；inst 是 C lib、沒有 `aos-inst` 命令列（§ 20；使用者 10-22「對於python版，aos-inst指令可以刪掉了，跟C++版一樣做成lib就好。」），單子交給 aos-exec 公開 API 的 `run_inst`。aos-exec 收旗標、讀入口資料夾的 `.env`（[N-58、N-59](NORMS/10-基礎設施-定義與工作區.md)，[ideas 10-21](../thinking/2026-10-21-ideas.md#4-aos-exec-支援-env10-21)）。

**命名**（[thinking 2026-10-23-naming](../thinking/2026-10-23-naming.md)，使用者「都先幫我統合。統合好後更新文件和artifact，我等一下重看」；條文裡的使用者原話不動）：

- loop.json 與 fsm 格要跑的東西都叫 `exec`（使用者：「fsm.json，現在是用val，幫我改成exec」；「exec，loop／daemon 的 run 也一起改 exec」）。
- fsm trace 一行是 `{"started_at","state","code","signal","elapsed_ms"}`，`started_at` 是 ISO 8601 到毫秒（P-07、P-38）。時間點＝C-54 命名方法 R6「時間點＝`<發生了什麼>_at`」（使用者 10-25「state.json中，runs改counter，at改成recorded_at」，回頂層兩題「都好」，頂層代定、可翻案）；其他 JSON 的命名見 [NORMS.md](NORMS.md)。
- 指示詞的檔內位置只認 `#/`。計數說「次」（使用者「我們都是說"次"」）。
- 純文字檔帶 `.txt`（fsm 的 `state.txt`、daemon 小格的 `stderr.txt`、demo 的 `current.txt`／`plan.txt`、P-13 的 `prompt.txt`／`answer.txt`）；`AOS_STACK` 預設 `$AOS_WS/.stack/`；題目資料夾 `new/`（認領搬 `cur/`、做完 `done/`，答案 `out/`）；10-30 起新 agent 的輸入是 `$AOS_STACK/queue/`，題目資料夾留給舊協議（P-11 的 10-30 改口、P-42）。
- 入口預設名 `_entry`（`AOS_ENTRY` 預設值、入口檔、JSON 的 key；使用者「改。然後_開頭=附註這個概念刪掉。」，原話裡的 `_exec` 照留）；不認得的 key 一律忽略（「不認得的key就是忽略」，C-48），`_` 開頭沒有特別意思。

**腦的工具呼叫**＝**P-41**（第七節；[thinking 2026-10-23-tool-calls](../thinking/2026-10-23-tool-calls.md)，使用者「litellm我開了，去做吧。」「盡量都用gpt的」）：工具資料夾裡的 `tool.json`（10-28 起改名 `_tooldef.json`、清單改由 agent 資料夾的 `tools.json` 登記，[aos-tools](../bin/README.md)）給模型看、`arguments` 從 stdin 進、stdout 出、對話落在 `$AOS_STACK/history.jsonl`、三態不變、五種錯。範本是 [demo/agent-dan](../demo/README.md)。10-28 起照 [agent-round](../thinking/2026-10-28-agent-round.md) 拆成格的 agent：腦是 `endpoint/<名>` 格（P-23）、history 只有 compact 可改寫（P-41）、格經 `parts.json` 登記（P-25）、每格拿 agent 資料夾當第一個參數（P-33）、`on_error` 預設停（P-20），各條的 10-28 加註。

## 分檔

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [01-保證佈局入口.md](CONVENTION/01-保證佈局入口.md) | 一、aos 保證的（不是慣例，是底）；二、佈局（每檔一句）；三、入口、loop、fsm |
| [02-題目stack停錯腦.md](CONVENTION/02-題目stack停錯腦.md) | 四、題目與答案（含 10-30 P-11 改口成 queue、P-42 agent 對話協議〔10-30 夜改口：外部 coding agent 也只碰這三樣〕、P-43 外部 coding agent〔eca〕的定義）；五、stack；六、停與錯；七、腦與工具（含 P-41 腦的工具呼叫） |
| [03-shell版與inst版.md](CONVENTION/03-shell版與inst版.md) | 八、shell 版與 inst 版 |
| [04-範例三種寫法.md](CONVENTION/04-範例三種寫法.md) | 八之「範例：同一隻 agent 的三種寫法」 |
| [05-不管落實待決.md](CONVENTION/05-不管落實待決.md) | 九、慣例不管的；十、程式對這份的落實（只有 impls 的 C++ 版，aos-tick 例外）；十一、要使用者決定的 |
| [06-巢狀.md](CONVENTION/06-巢狀.md) | 十二、巢狀：層層疊疊 |
