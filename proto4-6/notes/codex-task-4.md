# 任務書 4：Python 版補 `$b64`（跟 Lua 版對齊）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改 `proto4-6/step_common.py`、`aos_step_py.py`、`aos_py.py`、`test/test_step_py.py`、`README.md`**。不要 commit／push、不要開 agent。先讀 `proto4/notes/23-step-json-python.md` §23.6 的 binary 約定、`proto4-6/lua/json.lua` 怎麼做的、`aos_step_py.py` 現在 state 怎麼存讀。

要做：state 存檔時 `bytes`／`bytearray` → `{"$b64":"<base64>"}`（`json.dumps(default=…)`）；讀檔時只有一個 key 且是 `$b64` 的物件 → `bytes`（`object_hook`）。`aos_py` 加 `b64(b)->str`、`unb64(s)->bytes`。測試加 3 條：state 塞 `b"\x00\xff\x01"` → 狀態檔裡是 `{"$b64":"AP8B"}`、下一格讀回相等的 bytes；`aos.b64`／`unb64` 往返；Lua 寫的狀態檔（手寫一份含 `$b64`）Python 讀得回 bytes。README「逐步 Python」那段加一句 binary 規則（跟 Lua 那段同一句，或抽到共通段）。全套 `python3 -m unittest discover -s test` 要綠（52→55）。回報四行。
