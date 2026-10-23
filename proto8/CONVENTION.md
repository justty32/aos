# aos agent 慣例（2026-10-19 結論版；10-19 從 proto8-2 併入 proto8）

← [proto8](README.md)｜原話與拍板：[thinking/ideas](thinking/2026-10-19-ideas.md)｜跟 proto8 原則相撞的七條，使用者已全部裁定：[ideas § 9](thinking/2026-10-19-ideas.md)｜proto8 原則：[CONCEPTS](CONCEPTS.md)、[NORMS](NORMS.md)｜程式：[impls](impls/README.md)（10-23 起 C++ 是唯一實作；aos-tick 例外，在 [bin](bin/README.md)）、[demo](demo/README.md)

**aos 本身只保證環境變數（原三個，10-19 下班前加 `AOS_CF`、`AOS_CD` 成五個，§ 19；10-21 晚加 `AOS_CO` 成六個）和一支 `aos-exec`**（使用者 § 4；已升成規範 [N-57～N-62](NORMS/10-基礎設施-定義與工作區.md)）。其餘全是慣例：我們自己人寫 agent 時照抄的標準形狀，照抄的人不用想、看別人的 agent 一眼就懂（C-54）。**agent-bob 現在的樣子就是標準，stack 裡面自由**（拍板點 1）。

每條後面括號是依據：§ 幾＝[ideas](thinking/2026-10-19-ideas.md) 裡使用者原話的段號；拍板點 1～3＝ideas § 8；C-xx／N-xx＝proto8 的概念與規範；引不到的、這份自己定的，標「本稿定」。**10-19 第二輪**（§ 10）：範本改成混合寫法（第二、三、八節改寫）、巢狀層層疊疊的規則（第十二節 P-32～P-39）。**10-19 下班前～晚**（§ 14～§ 21）：入口放寬成四種、`aos-exec XXX`、五個環境變數、`#/` 尋址、impls 只提供 aos-exec 一支命令列（§ 23 之後 impls 也有 aos-loop、aos-fsm）——P-05、P-26、P-28～P-31、P-33、P-36、P-39 加註，新增 P-40（JSON 入口怎麼寫）；§ 21「舊版一起改」之後 `proto8/bin` 也跟上了，第十節改記兩版仍不同的地方（10-23 Python 版刪了，第十節改標成現況、兩版差異留作 10-23 前的紀錄）。

> **實作（10-23 起只有 C++ 的 [impls](impls/README.md)，aos-tick 例外）**〔10-23 註：Python 版刪了（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 也改 C++、tick 先留 Python），`proto8/bin` 只剩 `aos-tick`；這段原標「兩版實作」，以下講兩版、bin 版的是 10-23 前的樣子。條文裡講 bin 版的句子同此〕：`proto8/impls/aos-exec`（使用者假日的 C++ 參考實作，10-23 起進 git）與 `proto8/bin`（Python）都已照 § 14～§ 21 做。慣例本身（佈局、fsm 表、stack、題目與答案）兩版一樣；仍不同的只有「有哪幾支命令列、單子交給誰跑」：impls 提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列（loop／fsm 10-19 晚照 [ideas § 23](thinking/2026-10-19-ideas.md) 重寫／新做，daemon 10-21 照 bin 版重寫）、inst 是 C lib、沒有 `aos-inst` 命令列（§ 20），單子交給 aos-exec 公開 API 的 `run_inst`；bin 版原本另有 `aos-inst` 命令列（10-22 使用者「對於python版，aos-inst指令可以刪掉了，跟C++版一樣做成lib就好。」，已刪），單子在行程內呼叫 `aos_inst.run()`。所以底下提到 `aos-inst`（命令列）的句子是 10-22 前 bin 版的樣子、現在兩版都沒有；`aos_inst.run()` 是 bin 版的庫函數，各條標明；`bin/aos-fsm` 指 bin 版那支，impls 有對應的 `impls/aos-fsm`。10-21 aos-exec 收旗標、讀入口資料夾的 `.env`（[N-58、N-59](NORMS/10-基礎設施-定義與工作區.md)，[ideas 10-21](thinking/2026-10-21-ideas.md#4-aos-exec-支援-env10-21)）bin 版已做，impls 10-21 晚也對齊了（連同 10-21 下午、傍晚 loop／fsm／daemon 的改動；impls 沒有 aos-tick）。

**10-23 命名統合**（[thinking 2026-10-23-naming](thinking/2026-10-23-naming.md)，使用者「都先幫我統合。統合好後更新文件和artifact，我等一下重看」）：只換名字、不改原意——loop.json 的 `run` → `val`（P-06、P-27、P-28、範例）、trace 的 `ms` → `elapsed_ms`、`at` 改 ISO 8601 到毫秒（P-07、P-38）、指示詞 `at` → `$at`〔同日再刪，只認 `#/`〕、「圈」改「拍」（原話不動；10-23 晚再改「次」，使用者「我們都是說"次"」）；使用者 10-23 逐條重看代定後再改三處：純文字檔帶 `.txt`（fsm 的 `state.txt`、daemon 小格的 `stderr.txt`、demo 的 `current.txt`／`plan.txt`）、`AOS_STACK` 預設 `$AOS_WS/.aos/` → `$AOS_WS/.stack/`、題目資料夾 `inbox/` → `new/`（認領搬 `cur/`、做完 `done/`，答案照舊 `out/`）；慣例與範本（P-07、P-10～P-14、P-16～P-18、P-31、P-32、P-34、P-38、範例）跟著改，P-13 附檔資料夾的 `prompt`、`answer` 也帶 `.txt`。舊名在歷史敘述裡照留、旁邊加〔10-23 統合…〕註。10-23 晚使用者翻案（「改，beats改runs，然後val寫要跑啥，通常不會用val，應該用run。」，衝突時選「只有 loop、daemon 用 run」）：loop.json 改回 `run`（fsm 格仍是 `val`）、state 的 `beats` → `runs`、「拍」→「次」。10-23 深夜再改（使用者：「fsm.json，現在是用val，幫我改成exec」；問到 loop／daemon 時：「exec，loop／daemon 的 run 也一起改 exec」）：loop.json 的 `run`、fsm 格的 `val` 都改 `exec`（P-06、P-07、P-09、P-22、P-27～P-29、P-36、P-39、範例）。

**10-23 晚入口改名**（[thinking 2026-10-23-naming](thinking/2026-10-23-naming.md)，使用者「改。然後_開頭=附註這個概念刪掉。」「不認得的key就是忽略」）：入口預設名 `_exec` → `_entry`（`AOS_ENTRY` 預設值、入口檔、JSON 的 key；使用者原話裡的 `_exec` 照留）；不認得的 key 一律忽略（C-48），`_` 開頭不再有特別意思。

**10-23 腦的工具呼叫**（[thinking 2026-10-23-tool-calls](thinking/2026-10-23-tool-calls.md)，使用者「litellm我開了，去做吧。」「盡量都用gpt的」）：新增 **P-41**（第七節）——工具資料夾裡的 `tool.json` 給模型看、`arguments` 從 stdin 進、stdout 出、對話落在 `$AOS_STACK/history.jsonl`、三態不變、五種錯；P-08、P-23、P-24 加註。範本是 [demo/agent-dan](demo/README.md)。

## 分檔（2026-10-20 tidy：本檔超過 8 KB，按節逐字下放）

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [01-保證佈局入口.md](CONVENTION/01-保證佈局入口.md) | 一、aos 保證的（不是慣例，是底）；二、佈局（每檔一句）；三、入口、loop、fsm |
| [02-題目stack停錯腦.md](CONVENTION/02-題目stack停錯腦.md) | 四、題目與答案；五、stack；六、停與錯；七、腦與工具（10-23 加 P-41 腦的工具呼叫） |
| [03-shell版與inst版.md](CONVENTION/03-shell版與inst版.md) | 八、shell 版與 inst 版 |
| [04-範例三種寫法.md](CONVENTION/04-範例三種寫法.md) | 八之「範例：同一隻 agent 的三種寫法」 |
| [05-不管落實待決.md](CONVENTION/05-不管落實待決.md) | 九、慣例不管的；十、程式對這份的落實（10-23 起只有 impls 的 C++ 版，aos-tick 例外；兩版差異留作 10-23 前紀錄）；十一、要使用者決定的 |
| [06-巢狀.md](CONVENTION/06-巢狀.md) | 十二、巢狀：層層疊疊（10-19 第二輪） |
