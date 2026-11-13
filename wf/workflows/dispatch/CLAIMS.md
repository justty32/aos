# dispatch／CLAIMS — 領地登記（現役、保留、歷史）

← [dispatch](README.md)｜規矩在 [README § 流程](README.md#流程)：線只能追加自己那一格；收線移除與歷史整理歸調度者；沒有完成證據就不算收線。

### 現役

| 線 | 可寫目錄 | 唯讀 / 禁區 | 上線時間 |
|----|---------|------------|---------|
| 併入線（workflows 模板併入 aos 的第 3、4 塊；備料 `01959ce`〔改寫前 `f3d70ea`〕，模板 repo 已 push、家機或公司機都能做，下次開工由調度者開線落檔） | 開線時再定；計畫在 [workflows-into-aos](../../../proto8/thinking/2026-11/13/workflows-into-aos.md#第-34-塊落檔計畫先不落檔等調度者通知) | 只併 kernel 薄流程與 dev 包（W21＝B）；模板 repo 唯讀 | 還沒上線 |

### 保留給調度者，任何線都不得寫

| 目錄 | 理由 |
|------|------|
| `AGENTS.md`、`wf/` 的 hub 檔（`INDEX`／`WORKFLOWS`／`SESSION-LOG`／`WAIT_USER`）| 多條線同時動會互相打架，收線時由調度者統一更新 |
| 主工作樹的 commit 權 | 同一時間只有一隊在主工作樹 commit；其他隊用 worktree（見 [resources](../resources.md)）|
| 本表既有內容、交接書目錄 | 線只能追加自己那一格 |

### 歷史（收線後移來，附完成證據）

收線時間：各線的結果檔都沒寫幾點收線，這欄記的是該線最後一個 commit 的時間（11-13，台北）。

| 線 | 完成證據 | 收線時間 |
|----|---------|---------|
| 線乙（程式碼庫整理續做四批：舊路徑、agent-fsm 重複收一支、說明清舊、do_task 摺疊被砍） | `20d0f7f57`、`041df518b`、`1f6422272`、`4696428dd`；結果檔 [line-b-cleanup](../../../proto8/thinking/2026-11/13/line-b-cleanup.md)（全套 66 夾 1357 例只紅既有的） | 11-13 10:08 |
| 線丙（外部 MCP 接真的別人寫的 stdio server，只實測沒改 proto8） | 結果檔 [external-mcp-real-server](../../../proto8/thinking/2026-11/13/external-mcp-real-server.md)（隨 `22f669c0e` 進 git） | 11-13 10:22 前 |
| 主 session 四題、a2a 調查、eca_main 來信七項評估（三條只規劃／評估的線，沒有線名） | 結果檔 [main-session-in-aos](../../../proto8/thinking/2026-11/13/main-session-in-aos.md)、[eca-a2a-notify](../../../proto8/thinking/2026-11/13/eca-a2a-notify.md)、[eca-main-six-fixes](../../../proto8/thinking/2026-11/13/eca-main-six-fixes.md)（隨 `22f669c0e` 進 git） | 11-13 10:22 前 |
| 線己（kernel 框架上午：批 1a、2、3、11a、7a；10:25 這條線的子 agent 誤停使用者的樹，見[開工紀錄第十一節](../../../proto8/thinking/2026-11/13/kernel-framework-開工.md#十一事故子-agent-誤停使用者的樹11-13-1025)；下午由線己二接手） | `747c48ca9`、`cc5130d69`、`8d05ad5d5`、`3ea5123d2`、`54623831f` | 11-13 10:42 |
| 線庚（eca_main 來信第 7、6、3、1 項、外部 MCP 實測三題、`set-def`） | `a89759e57`、`ee906d9ee`、`57b7539cb`、`0b0aaf106`、`a4ae7d573`、`1b9fcec2b`、`f225b4754`、`88c571674`、`ab19068d0`；結果檔 [fixes-施工結果](../../../proto8/thinking/2026-11/13/fixes-施工結果.md)（`4aafb382e`；全套 66 夾 1412 例只紅既有 4 支） | 11-13 10:51 |
| 線辛（精選頁裁定的施工：W8、U4、U6、沙箱那句、範本掛 `jsonx`、feedback 路徑；新檔 convention-vs-agent-fsm） | `d103cdcd5`、`ba3efc807`、`916e3d34c`、`796e93cbb`、`2e1e69de2`、`981dc1859`、`412680c03`、`800cdbf4a` | 11-13 10:51 |
| 線癸（壞連結、「判官」字樣、eca-8 剩的一行、cl-9、進度看板路徑、線乙留的兩處文件） | `3905b61a2`、`e41c09ffb`、`c39fc540a`、`d57f21367`、`2856f3b45`、`85651ce3f` | 11-13 11:08 |
| 線丑（第二輪條文類 22 題照裁定改條文） | `33b61ff81`、`d159a6369`、`b0a4bb850`、`e6c9ab70e`、`b2ad81bbe`、`a1878c378`、`c38af8866`、收尾 `61dca0af1` | 11-13 11:25 |
| 線辰（知識庫跟上 ops-agent 六點的純文件部分） | `b44b6ce1a` | 11-13 11:29 |
| 線寅（fx-2:A 工具印的路徑照叫方的 stack 算） | `841e61912`、`909b076ad`、`869fa19ff`、`829c07be5`、`1be8cbcb5`、`62dda2703`；結果檔 [tool-stack-path](../../../proto8/thinking/2026-11/13/tool-stack-path.md)（`7cd69be72`） | 11-13 11:32 |
| 線壬（eca 通知改走 a2a 的施工） | `24a3f797d`、`c375dd672`；結果檔 [a2a-施工結果](../../../proto8/thinking/2026-11/13/a2a-施工結果.md) | 11-13 11:38 |
| 線午（a2a 施工後條文跟上、記四題裁定） | `1dd1a3ec8` | 11-13 12:03 |
| ops-agent 六點建議的評估線（只讀沒施工，沒有線名；結果檔交給線巳 commit） | 結果檔 [ops-agent-six-suggestions](../../../proto8/thinking/2026-11/13/ops-agent-six-suggestions.md)（`2c3f853c1`） | 11-13 12:03 前 |
| 線未（kernel 框架站照規則分流） | `7694e05f7`（kernel tests 51 例 OK、鏈劇本 6/6）；[開工紀錄第十三節](../../../proto8/thinking/2026-11/13/kernel-framework-開工.md#十三照規則分流線未hook-替單封信指定下一站) | 11-13 12:12 |
| 線巳（ops-agent 六點裡要做的五件：A1、A2、B1～B3） | `d23e1528e`、`dee207ef8`、`2c3f853c1`、`2e907fb4e`、`be818bcbd`；結果檔 [ops-fixes-施工結果](../../../proto8/thinking/2026-11/13/ops-fixes-施工結果.md) | 11-13 12:21 |
| 線申（agent 當 kernel 的設計與暫存樹原型，真 haiku 跑通） | [eca-as-kernel](../../../proto8/thinking/2026-11/13/eca-as-kernel.md) 第一～九節與 [01 原型實跑](../../../proto8/thinking/2026-11/13/eca-as-kernel/01-原型實跑.md)（檔由線酉的 `6f83a431a` 帶進 git） | 11-13 13:07 前 |
| 線酉（kernel 第二輪七題、留著等表態、工具包 `kernel_gate`、`route_ordered`） | `6f83a431a`、`306078925`、`0fe01b6b8`、`12942854f`、`9be257271`、`dd32bef00`、`1c973e47e`、`d8384df9b`、`adee4511d`、收尾 `fd9ae490a`；[開工紀錄第十四節](../../../proto8/thinking/2026-11/13/kernel-framework-開工.md#十四下午線酉kernel-第二輪七題的裁定留著等表態agent-當門) | 11-13 13:36 |
| 線天（一段文字可以寫成字串或字串陣列：`index_view`、`index_check`、`index_gen` 與 knowledge 說明） | `2c8020148`；結果檔 [text-as-string-array](../../../proto8/thinking/2026-11/13/text-as-string-array.md) | 11-13 14:04 |
| 線地（`wf/tools/json_text` 折行修正、拆成兩支） | `b374ac376`、`a5ab5d4dd` | 11-13 14:51 |
| 線玄（workflows 模板併入 aos：調查＋意見稿、使用者裁定、第 1 塊進 `proto8/knowledge/wf/`） | `2784848aa`、`bf305f206`、`745975e82`、`159414053`；結果檔 [workflows-into-aos](../../../proto8/thinking/2026-11/13/workflows-into-aos.md) | 11-13 15:00 |
| 線黃（`index_check` 假綠五案例、archive 夾跳過） | `2b0d36095`、`c0f37b872`；結果檔 [index-check-false-green](../../../proto8/thinking/2026-11/13/index-check-false-green.md) | 11-13 15:19 |
| 線己二（kernel 框架下午：找下一站三段、批 4、批 8、9、批 5 前半、停樹換檔；批 5 接線、批 6、批 10 留成 repo 外補丁沒進 main） | `4fcb631fd`、`42870fa27`、`df1c25ff2`、`bb4204242`、`d5f276737`、`da54d416f`；停樹換檔：釘 `159414053` 全套 68 夾 1592 例只紅既有 4 支、15:24 `swap.sh` 全過、15:29 `verify.sh` ALL PASS，備份 `~/code/kf2-1113/stop-tree/backup-1113-152418/` | 11-13 15:29 |
| 線戌（kernel 批 1b：agent 的 `hooks.py` 改用共用引擎） | `56a7fe498` | 11-13 15:50 |
| 線卯（repo 的 index：文件區 25 份、程式區 8 份，生成器與檢查腳本） | `418e17927`、`a993379be`、`e5c365457`、`ebe6836ba`、`6c939aed0`、`fe4908ba9`、`24df73f61`；結果檔 [index-build](../../../proto8/thinking/2026-11/13/index-build.md) | 11-13 15:56 |
| 線玄續（workflows 併入第 2 塊：工作流節點骨架＋tidy 一組進 `knowledge/wf/`） | `dbefe6fd2` | 11-13 15:56 |
| 線宇（8 KB 三處改推薦語氣、附錄 4 hook 那列、`env.sh` 正本進 `proto8/extras/aos-home/`） | `9f60cb0d8`、`2a6087735`、`40dc42b57` | 11-13 16:02 |
| 桌面頁線（收工待裁頁 24 題、優先裁頁、回覆讀回與逐題落地表） | `ecb0a71c5`、`bee7707f0`、`3cb2cb267`、`e46d27653`；[收工待裁-回覆落地](../../../proto8/thinking/2026-11/13/收工待裁-回覆落地.md) | 11-13 16:30 前 |
| 線宙（push 前隱私修兩筆） | `5a87aa55b`、`233ca54fa` | 11-13 16:30 前 |
| 線洪（刪掉 wf-lint；只照 grep 逐句改、沒通讀，下次開工再掃一次） | `70e6d4fd8` | 11-13 16:34 |
