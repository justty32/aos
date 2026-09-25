# arknights 真實專案（2026-09-25）

拿 proto5 的 agent 團隊去做 `~/repo/narratives/arknights`（明日方舟全劇透設定集）的「一批 3 個次要角色補檔」。路線：強模型做 → 找重複流程 → 換笨模型 → 換確定性程式；每次降級都用同一套評分比。

| 子夾 | 做什麼 | 誰 |
|---|---|---|
| [eval/](eval/README.md) | 第 1 段：基準集 15 人＋評分器（機械／證據／評審／量測，一鍵 `eval.sh`） | 本隊 |
| [team/](team/README.md) | 第 2 段：強模型版團隊設定與試跑（名冊、人格、門房、1 人＋1 批真跑、哪些步驟是機械／語感／強模型） | 另一隊 |

程式：`proto5/examples/arknights/eval/`（評分器）、`proto5/examples/arknights/`（另一隊的團隊設定）。
