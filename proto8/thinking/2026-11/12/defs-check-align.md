# 定義檢查與條文跟實作對齊（Q10）：eca-claude 已經過、defs 對「一份定義」照查它自己的名字，C-42 續與 C-52 ⑧ 照現行三支改

題目出處：[agents-split § 留給使用者](../10/agents-split/README.md#留給使用者) 第 4、5 點。

## 使用者原話與決定

- 11-12 使用者對 Q10 答「a」（隊長轉述）＝照現在的實作把檢查和條文修齊；原則推不出、要做方向判斷的不改，列出來。

## 結論

- **eca-claude 範本**：11-12 實跑 `lib/aos/defs` check（root＝`templates/eca-claude`）是 `{"problems": []}`、退 0——缺 `README.md`／`_metainfo.json` 的事已經不在，不用改。
- **資料夾自己的名字不查 → 已修**：root 本身就是一份定義（`agent_def` 的 check 就這樣叫）時，改查這個資料夾自己的名字（`[a-z0-9_-]+`，不合＝`definition folder name '…' must match [a-z0-9_-]+`）。理由：同一份定義放在樹裡檢查會查名字、單獨檢查卻不查，結果不該看從哪裡叫。樹的根不是定義時，根自己的名字照舊不查。`lib/aos/defs/catalog.py`、測試 `test_root_is_one_definition`（拿掉修法時會紅、修後綠）。
- **路徑一律顯示 `.` → 照現行，不改**：README 本來就寫「輸出路徑相對 root」，root 就是那份定義時相對路徑就是 `.`；要改成別的（絕對路徑、資料夾名）得選一種新寫法，原則推不出。已在 defs README 寫明。
- **空資料夾算過 → 照現行，不改**：README 本來就寫「根指向空目錄時回空清單」；defs 的 check 是查「找到的每份定義」，沒找到就沒有問題可報。「交進來的這個夾是不是一份定義」是叫它的那一層（`agent_def`）的事，不歸 defs 判（C-52 只管自己這一層）。已在 defs README 寫明。
- **C-42 續**：主句裡舊 `lib/agent/agents`（add／say／ask／rm／ls）直接改寫成現行三支 `subagent`／`agents_ctl`／`agent_def`；「生子 agent 兩種」那條改成 `agent_def new`／`subagent add`／`agents_ctl add`、`ws` 收在兩支的 `add`（沒給＝沿用父的 `$AOS_WS`，照 `aos-agent ctl add` 實作）；上限那條改寫成兩道關的現況（`max_subagents` 預設 4、判官 `max_running`、`agents_ctl` 不數）。原本補在後面的「11-10 深夜註」併進主句後拿掉。
- **C-52 例外 ⑧ → 拿掉**：現行三支成功時只把下層 stderr 原樣透到自己的 stderr、stdout 不附（`lib/agent/agents_cmd.py` 的 `run`；`agent_def` check 也只印 defs 的 JSON），合判準；現行表只列現在有效的，所以整列刪。⑤ 的 11-06 註與主檔那句裡的 `agents` 改成三支。

## 代定（可翻）

- 單一定義名字不合時的原因句用新的一句（`definition folder name '…' must match [a-z0-9_-]+`），不沿用樹裡那句「path segments」。

## 留給使用者

- 空資料夾交給 `agent_def check` 照樣算過：要不要讓 `agent_def` 先確認 `path` 本身是一份定義（有 `interfaces.json` 或 `_metainfo.json`）？這是 `agent_def` 那層的事，這次沒動。
- 附帶看到、沒動：`templates/` 整棵 check 報 `judge-llm`、`tool-python` 兩個工具範本缺 `interfaces.json`（defs 把只有 `_metainfo.json` 的夾也當定義、ls 列得出來，check 卻要 `interfaces.json`）；名字規則允許連字號（`agent-fsm`、`eca-claude`），C-54 字面是「小寫加底線」。
