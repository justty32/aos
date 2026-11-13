# user_zone_guard（不是給腦的工具）：before_tool 的 hook handler，aos 工具的參數路徑落在使用者專區、又不在它的 mailbox/ 底下（工具也不是唯讀）就擋

← [使用者專區段 2 施工](../../../thinking/2026-11/13/user-zone-plan/08-段2施工.md)｜知識庫 [aos/user_zone.json](../../../knowledge/aos/user_zone.json)

- 做什麼、怎麼認路徑：看 `_entry` 檔頭；`_entry --help` 印英文用法。
- 只是紀律加一道、不是保證：eca 的 `before_tool` 只看得到 aos 工具，CLI 自己的 Bash／Write 擋不到（知識庫 `aos/body.json`）。
- 範本預設不掛。要掛：`self_hook` `{"op": "add", "event": "before_tool", "name": "user_zone_guard", "path_json": {"$env": "AOS_HOME", "$path": "/lib/agent/user_zone_guard"}, "on_error": "continue", "timeout_ms": 5000}`。
- 測試：`proto8/lib/agent/tests/test_user_zone_guard.py`。
