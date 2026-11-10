# packs — 通用工具分四包，每包一份工具清單

使用者 11-10 深夜：「最基礎的就是read/ls/view/stat要有。然後是普通的編輯如write/edit/copy/move/mkdir，再來是trash/remove，最後是shell。就是說，這是一包一包的」；「1.預設開到第四包，想要安全就自行限制」。

| 包 | 檔 | 工具 |
|---|---|---|
| 1 看 | [look.json](look.json) | read、ls、view、stat、json_read |
| 2 改 | [change.json](change.json) | write、edit、copy、move、mkdir、json_write |
| 3 刪 | [delete.json](delete.json) | trash（丟進工作區 `.trash/`，可搬回）、remove（真的刪） |
| 4 殼 | [shell.json](shell.json) | shell（bash 一行指令）、run_python |

每份就是一般的工具清單（`{"tools": {名: {"path": …}}}`，路徑寫 `{"$env": "AOS_HOME", "$path": "/lib/base/…"}`，整夾 `cp -r` 出去仍通）。範本的 `tools.json` 用 `"$override": [look, change, delete, shell]` 疊上自己那批；關掉一包＝從那串拿掉它，關掉一支＝`aos-agent tools rm 名`（寫 `"名": null`）。工具本身不擋工作區外的路徑（相對從 `$AOS_WS` 算、絕對照用），能不能動看 Linux 權限。
