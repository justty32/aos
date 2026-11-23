工作室裡東西放哪裡的問答表、各位子的寫入範圍為什麼只是約定、位子的定義怎麼指向角色卡（標〔提案〕的＝提案，fable 規劃，11-23，等使用者定）。

# 東西放哪裡、能寫哪裡

← [org](README.md)｜地盤規矩 [wf/ws](../ws/README.md)

## 東西放哪裡

照順序往下問，第一個答「是」的就是它的位置：

| 問題 | 放哪裡 |
|---|---|
| 是程式、範本、知識庫、條文嗎？ | `proto8/` 對應的夾（哪個夾負責什麼查 [code map](../knowledge/code-map.json)） |
| 在講「誰負責什麼、做完交給誰」嗎？ | `wf/org/`（只放入口與角色卡） |
| 在講「一類事怎麼做」、大家共用嗎？ | `wf/workflows/`；坑與做法投 [wf/public](../public/README.md)，對 aos 的意見投 [wf/advices](../advices/README.md) |
| 是某個位子自己的筆記、提案、草稿、任務書、自己做的定義夾嗎？ | 它的地盤 `wf/ws/<上層>/<名>/`（[規矩](../ws/README.md)） |
| 是討論紀錄、調查、規劃、報告嗎？ | 當天的 `proto8/thinking/<年-月>/<日>/` |
| 是還沒做完的事嗎？ | [wf/progress.json](../progress.json)；要換 session 的交接寫 [HANDOFF](../HANDOFF.md) |
| 是要問使用者的題嗎？ | 使用者專區；沒有專區的機器照 user.md「wf/user」那列 |
| 是暫存、log、跑出來的產物、抄來的複本嗎？ | 地盤的 `temp/`（不進 git）；暫存樹在 `~/.aos/scratch/<線名-日期>/` |

位子的長期產出放它的地盤，`wf/org/` 不另開資產夾。[`wf/user/`](../user/) 是使用者的地盤，只讀。

## 寫入範圍只是約定

角色卡列的「可以寫」「唯讀」是講好的範圍，**沒有強制力**：全部 agent 用同一個 Linux 帳號，commit-request 不查誰交了誰的檔（[wf/ws 規矩 5](../ws/README.md)），配給包的「只寫自己的工作區」也只靠 system 文字（[kits「已知限制」](../workflows/dispatch/kits/README.md)）。硬限制是使用者之後要跟 eca-aos 談的題目，本夾不設計它。

在 `git status` 看到別人範圍裡的改動是正常的；自己範圍裡出現不是自己改的，停下來問 eca-aos。

## 定義指向角色卡〔提案〕

位子掛起來時，系統文字只寫「你是哪個位子；開工先讀 AGENTS.md、[org 入口](README.md)、你的角色卡、你的 `notes.md`」，職責與範圍以角色卡為準，不重抄。定義夾照地盤規矩放 `wf/ws/<上層>/<名>/`；這種定義現在一份都還沒做。打雜工用配給包、不讀角色卡，它那張卡是寫給派它的人看的。
