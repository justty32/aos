> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 已經定下來的與尚未拍板的
← [turn-based-folder](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

## 已經定下來的（不必再問）

- `aos inst` 這條子命令**直接刪掉**，只留 `aos exec`。
- 取件用 `rename` 成 `.runi`；`.runi` 已存在時**拒絕啟動**。
- 投遞寫進 `.aos/inst.tempd/<pid>.json`；彙整就是把它們併成 `.aos/inst.json.temp`，
  再 `rename` 蓋掉 `.aos/inst.json`。
- **一回合＝一整批**，不是一次一筆。
- 每筆 instruction 自己帶一個欄位，決定要不要開 thread 用 non-blocking 的方式跑；
  但 **`aos exec` 仍會等所有 thread 跑完才算本回合結束**。遇到 non-blocking 那筆之後，
  **下一筆立刻啟動**（真並行，不排隊）。
- 命名標準：`<名字>.<副檔名>.<狀況>`，第一個 `.xxx` 是副檔名、第二個是當前狀況。
- 持續執行是 `aos exec --loop 0`，不另做 `core/daemon`。
- **抽象 CPU 走投遞式，不在本回合同步跑完**：LLM CPU 是常駐 daemon，工作要求透過特定
  指令投遞到外部資料夾，完成後由它寫回來——「就類似 CPU 與 GPU 的交流」。因此 LLM 的
  結果落在**未來某個回合**，`aos exec` 那條「等所有 thread 跑完才算本回合結束」的邊界
  對它不適用。代價見 [call-format/cpu-analogy](../call-format/cpu-analogy.md)。

## 開放問題（尚未拍板）

- non-blocking 欄位會動到**凍結的核心層**：新增 JSON 欄位要改 `format.cpp`
  （不認得的 key 會被拒），thread 化要改 `exec.cpp`／`run.cpp`。落地前必須明確解凍。
- `aos exec --loop 0` 只監看一個資料夾，還是能同時管理多個；其生命週期與啟停介面。
- `aos agent start`／`init` 是否必須冪等，重複執行時要保留、重建還是拒絕既有狀態。
- 回合失敗的語意：停在原回合、進入失敗回合、重試，或交由使用者另投 instruction。
- 指令以指定資料夾為 cwd 執行時的信任、安全與權限邊界。
- **彙整用 `rename` 蓋掉 `inst.json` 會無聲吃掉沒被讀走的批次**（見下一條）。
- 彙整的**順序**：多份投遞併成一批時誰先誰後。pid 排序是確定性的但無意義；
  mtime 有意義但會平手。
- 彙整者**什麼時候跑**、由誰跑：`aos exec` 每回合自己跑一次，還是獨立的一步。
- 彙整時 `inst.json` 位置上已經有一份沒被讀走的批次：附加、等下一輪，還是拒絕。
- 彙整完的 `inst.tempd/<pid>.json` 何時刪除，以及刪除與發布 `inst.json` 的先後。
- 某份投遞內容無效時：隔離該檔繼續、整批停住，還是拒絕發布。
- `--loop` 的細節：間隔單位、`0` 的語意、要不要改用 inotify、收到信號怎麼收尾、沒有 `inst.json`
  時是等待還是結束。另外它遇到 `.runi` 會**永遠拒絕啟動**（因為規則是拒絕），這是
  預期行為還是要另開一個「清掉現場」的命令。
- 核心 CPU 在 `.aos/inst.json`、其餘在 `.aos/insts/` 是刻意的不對稱。代價是「列出所有
  CPU 的佇列」這種操作要對頂層那個特例化；可接受與否還沒確認。

> 本條目的「核心理想」與「最基礎使用方式」已由使用者定案；開放問題只是在落地前
> 必須回答的設計點，不改變上述回合制模型。
