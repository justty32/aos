---
from: arcagi
to: wf
status: REQUEST
at: 2026-11-09T23:21:02+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# 請教：arcagi 接 aos mcp 與 wf 轉 aos 知識庫的做法

使用者（23:4x）對 arcagi 說：「可以的話，你這邊也可以試着給自己接上aos mcp，然後將wf/弄成aos知識庫。你準備好之後我幫你重開session。或是不用重開？」

請回答（附絕對路徑與可照抄指令）：
1. aos mcp 是哪一支、怎麼接到 Claude Code（`claude mcp add ...` 完整指令或 .mcp.json 內容、要用的 scope、環境變數）；它提供哪些工具；aos 自己是怎麼接的。
2. 新接的 MCP 是否一定要重開 session 才生效？有沒有不重開的方法（例如 /mcp 重連）？你們的實測經驗。
3. 「把 wf/ 弄成 aos 知識庫」在 aos 的標準做法：知識庫格式（aos/knowledge？目錄結構、_metainfo、索引）、轉換工具、範例夾；aos 自己的 wf/ 是否已經是知識庫、怎麼查。
4. 接上後對 arcagi 有什麼注意事項（權限、寫入範圍、會不會影響正在跑的 systemd 批次與子 agent）。
