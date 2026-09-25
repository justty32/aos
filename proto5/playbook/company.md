# 當作開公司：組織圖（已落成 aos 裡跑得起來的東西）

← [playbook README](README.md)｜真東西：[examples/company/](../examples/company/README.md)｜規格：[company.md](../spec/team/company.md)、[market.md](../spec/team/market.md)｜報告：[2026-09-25-company](../notes/2026-09-25-company/README.md)

董事（使用者）：「就當做是開公司，業務就是產出 narratives……我要的是**用我們現有的 aos 體系去建立這個公司架構**。」
09-25 起這份不再只是比喻：公司是 [examples/company/](../examples/company/README.md) 這個樣板，`company.py new` 生一家、`up` 開工，每個部門是一支真的 aos 團隊，董事就是 `human`。
公司分兩層在看：

- **運轉層**（aos 裡）：部門＝團隊資料夾、員工＝名冊成員、部門之間的信＝機械總機。下表「aos 裡是誰」那欄。
- **施工層**（調度層，aos 外）：蓋這間公司的是 Fable 派的 Claude 隊；經理人（Fable）在市場層照表現撥額度。下表「施工期誰在做」那欄。

## 總表

| 單位 | aos 裡是誰（樣板名；開幾家時加前綴 `c1-`…） | 做什麼 | 施工期誰在做 | 對應的東西 | 狀態 |
|---|---|---|---|---|---|
| 董事會 | `human`：`company.py order／mail／answer`；各部門的 `team/human/` 收件匣 | 出資、下單、拍板、抽查 | 使用者本人 | [ask.md](../spec/team/ask.md)、`proto5/advice.md`（方向日記，不動） | 有（永遠是人） |
| 總裁 | 總裁辦 `teams/hq` 的領隊 `hq-lead`（lead 模板＋[總裁人格](../examples/company/persona/hq-lead.md)，gpt-5.5） | 董事的一句話翻成〔給 部門〕單、追到結案、回報董事 | Fable（調度者） | [company.md §3 總機](../spec/team/company.md) | 有（09-25 真跑 2 次） |
| 總裁辦 | `teams/hq`（只有總裁一人） | 接董事的單（門房 `routes.json`）、兼業務、兼 HR 決策 | Sonnet 文件隊（SESSION-LOG／WAIT_USER） | [route.md](../spec/team/route.md) | 有 |
| 業務部 | 併在 hq：hq 的門房（機械）＋總裁兼判斷 | 接單、把客戶的話翻成製造部認得的句型 | Fable 派隊 | route.md、[crystal.md](../spec/team/crystal.md) | 兼任 |
| 製造部 | `teams/mfg`：`mfg-lead`（經理，拆批次）、`mfg-writer1`（寫手）、`mfg-reviewer`（審查）；忙時經理 spawn 臨時工 | 補人物詞條：門房「補人物 X（只寫詞條）」直接開單給寫手，驗收＋審查過才交件 | 強模型 Claude 隊（手工線） | [examples/arknights](../examples/arknights/README.md)、[tasks.md](../spec/team/tasks.md)、[verify.md](../spec/team/verify.md) | 有 |
| 品管部 | `teams/qa`：`qa-inspector`（deepseek-chat）；評審＝`eval.sh` 裡一次性的 claude-opus-5 呼叫（臨時工） | 門房「驗貨 X」→ 抽 3 列證據回原文核對、寫 `qa-reports/X.md`；批次跑 eval 給市場排名 | Claude 隊寫評分器 | `examples/arknights/eval/`、[score-new-entries](workflows/score-new-entries.md) | 有 |
| 研發部 | `teams/rd`：`rd-smith`（工具匠，`tool_draft`） | 造工具、改流程；人批才裝 | Claude 隊 | [toolsmith.md](../spec/team/toolsmith.md)、[tools/](../tools/README.md) | 有 |
| HR | 併在 hq：HR 的擋點（這家 `K/hr/policy.json`，`up` 照 `company.json` 寫）＋`aos-team hr` 薪資表／試用；`spawn` 生臨時工；決策總裁兼、名冊董事改 | 編制、名額、考核、薪資（模型選型） | HR 部寫程式 | [hr.md](../spec/team/hr.md)、[spawn.md](../spec/team/spawn.md)、[score.md](../spec/team/score.md) | 兼任＋機械 |
| 圖書館 | `teams/lib`：`lib-librarian`（librarian 模板，deepseek-chat）；這家的 commons 在 `teams/commons/` | 收各部門投稿，機械審，像舊條目才叫館員判 | 文件隊（本 playbook） | [commons.md](../spec/team/commons.md)、[examples/commons](../examples/commons/README.md) | 有 |
| 財務部 | 沒有模型員工：帳本 `$AOS_COST_HOME`（`up` 傳進兩個池）＋公司帳戶 | 每部門／每單 token 與美元、預算、帳戶餘額 | 財務隊寫程式 | [cost.md](../spec/team/cost.md) | 純機械 |
| 總機（跨部門往來） | `company.py relay`（kernel 每 5 秒叫一次） | 〔給 部門〕的信 → 對方門房開單或窗口信；回覆照 reply_to 抄回 | — | [company.md §3](../spec/team/company.md) | 有 |
| 總務／資安 | 一家一個 kernel（池＝cpu 上限）、牆（bwrap）、郵差再驗 | 開機關機、名額硬上限、擋越權 | 審查隊＋內建機制 | [wall.md](../spec/team/wall.md) | 有 |
| 經理人（市場層） | aos 外：Fable 用 `market.py` | 幾家公司競爭：排名、撥額度、倒閉、合併 | Fable | [market.md](../spec/team/market.md) | 有（兩家真跑一輪，見 [market-run](../notes/2026-09-25-company/market-run/README.md)；沒五家真跑） |

**員工兩種**：正式員工＝名冊裡有家、`notes: true`、記憶留著（算人頭，新創 ≤10）；臨時工＝spawn 生的、一次性模型呼叫、機械程式（不算人頭，但跑起來佔 cpu）。名冊每個成員的 `employment` 寫是哪種（HR 部），`company.json` 的 `staff` 寫兼哪些角色。

## 公司節奏

一段＝一季：董事 `order` → 總裁派〔給 mfg〕→ 製造 → 總裁派〔給 qa〕→ 品管 → 總裁回報董事；季末經理人 `market.py score／rank`（品質、快、省）→ 花光的先倒閉 → `grant`、剩兩家合併；每隊收尾沉澱進 playbook（施工層）與 commons（運轉層）。
例行的（每週數一次積壓、每季跑一次 eval）用心跳 routines 派給對應部門，不用人記得。

## 新創 → 擴張

新創：正式 7 人（總裁、製造 3、品管 1、研發 1、館員 1）、cpu 12／20、llm cpu 5／5（cpu 不含 llm，同 HR）。擴張到頂（正式 100、cpu 200、llm cpu 20）每部門長成什麼樣，見 [examples/company/README.md〈擴張到 100 時〉](../examples/company/README.md#擴張到-100-人時長什麼樣)。
