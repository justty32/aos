# 子線 newbie：up／brain／mail／compact 與新手接口

線名 `newbie`。範圍：
- `modules/up/`（aos7_up.py、aos7_up_cli.py、aos7_up_brain.py、aos7_up_memory.py、aos7_up_ask.py、aos7_up_status.py、prompts/、README、ADVANCED）與 `proto7-2/QUICKSTART.md`：brain 多回合（`brain/task.json`、PROGRESS／停下信、每 5 步、3 步沒進展、40 步）、跨信記憶（`notes/done/`）、ask／`you` 信箱、status 六／七行、stop、前景訊號（FL 報告的 `handed` 已知 bug 是否已修？看 `git log -- proto7-2/modules/up`）。
- `modules/mail/`（白話化回信、done／read、events must 提醒、ack 游標）、`modules/compact/`（now／forget／watch、封存與換摘要、被殺恢復；longtask 報告說「compact jsonl 摘要無內容」是否已修）、`modules/skills/`、`modules/routines/`、`modules/wfnode/`。
- 對照新手試用與白話化的結論：`proto7-2/notes/play/2026-10-10-firstrun/README.md`、`2026-10-09-newbie/README.md`、`2026-10-09-longtask/README.md`（未修清單：brain＋llmcall 傳輸中被殺永久卡住、status 看不出卡住、跨信不記得、metrics 把多回合算重試——逐條查今天是否已修、修法是否和其他模組一致）。
- 用語一致：「練習用的 AI」「步／回合」「卡住」「NEEDS-USER／PROGRESS／DONE」在 up、mail、kernel 通知信、status、QUICKSTART、--help 是否一致。
- **新手接口 ELI5 後是否仍複雜**：從 QUICKSTART 走到第一封回信，列出新手必須知道的概念與指令數、要在哪個資料夾跑、出錯時看到的訊息是否白話。給具體可刪減建議（C 類）。
- 副作用：`aos7-up --help`、`status`、`ask` 唯讀與否；`stop` 留什麼；`up` 失敗半途留什麼。
