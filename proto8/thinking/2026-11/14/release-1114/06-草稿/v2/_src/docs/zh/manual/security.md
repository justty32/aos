# 安全說明
<!-- verified: 11-14 v2, the tools rm shell / run_python / tools reset block was run literally on a running tree; ann still answered afterwards -->

agent 會用你的 Linux 帳號執行程式，同帳號內沒有隔離：會開 shell 的 agent 碰得到你帳號碰得到的一切。請在專用帳號、VM、容器或丟了也不心疼的資料夾裡試。

<!-- copy:SEC -->
agent 會用你的帳號執行程式。請在拋棄式帳號、容器，或丟了也不心疼的資料夾裡試。沙箱是實驗功能。

<!-- source: 06-草稿/文案表.json SEC；03-計劃.md 4.1；proto8/templates/agent-fsm/README.md -->

## 為什麼

| 事實 | 意思 |
|---|---|
| agent 是一般的 Linux 行程 | 它能做你的帳號能做的事 |
| agent-fsm 範本預設開了很多工具包：看、改、刪、殼（shell、run_python）等 | 它可以讀寫刪檔、跑指令 |
| 這些檔案工具不擋工作區外的路徑（相對路徑從工作區算、絕對路徑照用） | 能不能動，只看 Linux 檔案權限 |
| 同一個帳號下的 agent 彼此沒有隔離 | 一隻 agent 能碰到同帳號的其他檔案與行程 |

假腦（L0）不會真的亂做事，但範本的工具與權限是一樣的；接上真腦（L1 以上）才是實際風險所在。

## 建議的做法

1. **拋棄式帳號**：另開一個沒有重要資料的 Linux 使用者來試。
2. **容器**：放進容器裡跑（本版沒有提供 Docker 映像，容器的跑法還沒實測）。
3. **丟了不心疼的資料夾**：至少把示範夾放在 repo 外（例如 `~/aos-demo`），不要把工作區設成放重要東西的地方。
4. **收緊工具**：從定義的 `tools.json` 的 `$override` 拿掉不要的包（例如拿掉 `shell.json`（殼：shell、run_python）與 `delete.json`（刪：trash、remove）兩包）；或只關一隻的某幾支，在 `~/aos-demo/tree` 底下執行：

   ```bash
   aos-agent -d stacks/root -t ann tools rm shell
   aos-agent -d stacks/root -t ann tools rm run_python
   ```

   這只改 ann 自己那份（第一次會印一行 warning，說它在 ann 的 stack 建了自己的 `tools.json`），定義不動；`aos-agent -d stacks/root -t ann tools reset` 可以回到定義。

## 沙箱是 L3 實驗

專案裡有沙箱與限額相關的零件（`aos-sandbox`、`aos-asuser`；需要 bubblewrap 等外部工具），**屬於實驗功能，還沒實測，不是安全保證**。demo 版明講沒有「安全隔離保證」。

下一步：[狀態](../status.md)、[疑難排解](troubleshooting.md)。
