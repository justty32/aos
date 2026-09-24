← [agent-access 提案](README.md)

# astra 唯讀審查任務書：agent 權限與工作環境提案

你是唯讀審查者。**不要改任何檔**，只輸出一份審查報告（繁體中文、白話）。

## 背景

使用者要：agent（例如 amy，家在 `./amy`）的工具能碰指定資料夾、不能碰 amy 自己的家；設定要常改、好改；共用工具夾可改名；workspace 有別名（amy 永遠看到 `ws/`，實際從 `~/ws-A` 換 `~/ws-B`）。
使用者定調：這些都是「工具存取的別名／映射」，**用指示詞（directives）表達**；隔離（bwrap）是附加的牆。

提案在 `proto5/notes/2026-09-24-agent-access/`：`README.md`（本體）、`options.md`、`env-flow.md`、`examples.md`、`experiment.md`（腳本在 `exp/`）。
相關規範：`proto5/spec/directives/`、`proto5/spec/inst-posix/`、`proto5/spec/agent/`（尤其 `info.md` §3.3、`directives.md`、`layout.md`）、`proto5/spec/aos-agent/`（`tick.md`、`send.md` §5.3、`register.md`、`cli-check.md`）、`proto5/spec/cpu/methods.md`、`proto5/spec/kernel/home.md`。
程式：`proto5/lib/aos_agent_batch.py`（`tool_inst`）、`aos_agent_home.py`、`aos_agent_info.py`、`aos_inst.py`、`aos_directives.py`。
base 工具包（另一隊，唯讀，可能還在變）：`/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a9264eb50d9daee3e/proto5/tools/`（`README.md`、`base/_common.py`）——若讀不到就只看提案裡的描述。

## 請審三件事

1. **漏掉的逃逸路徑**：在「最小版」（現有指示詞＋每支工具 `_meta.argv` 前面接 bwrap）與「完整版」（`aos-jail` 讀 `access.json` 組 bwrap）下，工具（尤其 bash）還有哪些方式碰到映射表以外的東西、改到自己的權限、或影響別的 agent／kernel？
   例如（不限於）：`/proc`、`/dev`、`/etc` 掛進去的後果；`--ro-bind /usr` 夠不夠；aos-exec 在牢外開的 stdin／stdout／stderr 檔（`work/`、`log/`）；`work/N.in` 由 aos-agent 寫、工具輸出寫 `work/N.out`——模型能不能藉此寫到別處；唯讀蓋上去的單檔在原子 rename 後的行為；共用資料夾可寫時的下毒；網路；工具之間同一批平行跑的競態；`$ref` 指到的映射表如果放在牢裡可寫的地方。
2. **設定改動的手續是不是真的簡單**：`examples.md` 的每個情境，實際要動幾個檔、幾個指令；什麼時候生效（提案說「下一次叫工具」）是否跟現行規範相符（`tick` 每格重讀工具檔、`_meta` 送件時才解）；有沒有情境會卡住（例如已送出的批、崩潰恢復時重送用舊的 `work/N.inst.json`、刪掉映射的名字時 `cwd` 指不到）。
3. **跟現行規範的衝突**：提案的最小版與完整版有沒有違反現行規範的句子（例如 `info.md` 說「沒有欄位吃 `$opt`」、「送模型前 `_` 開頭 key 拿掉」、`_meta` 不能寫 `stdin`／`stdout`、inst-posix 的中心路徑規則、directives 對 `$opt` 的規定、`aos-agent check`）；實驗結果的解讀有沒有錯（例如 experiment.md 實驗 1 #3 的結論「共用檔裡的 `$ref` 相對各自 agent 家」）。

## 輸出格式

- 開頭一段總評（3～5 句）。
- **必修**：編號清單，每條「問題 → 為什麼 → 建議改法」，附檔名與行（或節）。只放真的會讓提案錯、或讓使用者踩坑的。
- **建議**：同格式，可不改。
- 不確定的標「待確認」，說怎麼驗。
