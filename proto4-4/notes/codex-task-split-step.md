# 任務書：proto4-4/src/step.janet 破 300 行（309），照 STRUCTURE.md 拆

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改 `proto4-4/src/`、`proto4-4/test/`、`proto4-4/README.md`**。不要 commit／push、不要開 agent。先讀 `STRUCTURE.md` 的拆檔規則、`proto4-4/src/step.janet`、`aos-step`（入口）。

把 `step.janet` 裡「狀態檔讀寫」那一群（pc／env.img／src／state／error／waiting 的 read／write／atomic-spit／path 之類）**原文搬**到新檔 `proto4-4/src/state.janet`，`step.janet` 用相對 import（看 `step.janet` 現在怎麼載 `aos.janet` 的，照同一種方式），入口 `aos-step` 不變。搬完兩檔各 300 行以下、行為零改變：三支測試（38／12／45）全綠；另外用 `diff` 證明搬過去的函式跟原本逐字相同（回報裡貼你怎麼比對的）。README 若提到檔名就補一句。回報四行。
