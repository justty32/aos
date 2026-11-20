# 線 shared-docs-1120：把 k1、k2 因檔被佔而沒補的字補進共用文件

任務：頂層雜活。依據 `aos-pylib-k1-1120.md` 末節與 `aos-pylib-k2-1120.md` 第 6 點，字照紀錄逐句搬，不另寫。

## 做了什麼（逐字取自紀錄）

- `proto8/py/README.md`：開頭那段 `tool_spec.py` 的句子換成 `aos.py.fn` 的句子（k1 末節第一條）；「現有工具不必遷移。」拿掉。
- `proto8/templates/README.md`：`tool.py` 那句換成 `aos.py.fn` 寫的加法（k1 末節第二條）。
- `proto8/py/docs/04-共用模組.md`：`aos.py` 那段加 `from aos.py import fn`（…）一句（k1）；`defs`＝`aos.agent_spec` 後補「（`defs.Agent` 的本體在 `aos.agent_spec_agent`）」（k2）；`spec_base` 那列後加 `spec_unit` 一列（k2）。
- `wf/tools/index_gen_desc.json`：`templates/tests/tool-python`、`templates/tool-python` 兩句說明改成 k1 建議的新句子。

## 沒加的

- 開工時三份文件都還沒有人補過這些字，全部都補。

## 替使用者做的選擇

- `spec_unit` 那列是三欄表，k2 只寫了前兩欄；第三欄「誰 import 它」我依 k2 紀錄（`Unit` 在 `agent_spec_agent`、`main(物件)` 在 `agent_spec`）填 `agent_spec`、`agent_spec_agent`。
