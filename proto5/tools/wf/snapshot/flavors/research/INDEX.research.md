| `index/` | **索引真相層**：一件材料一列、一類一檔，狀態欄即處理進度（維護規則 [workflows/common/index-rules.md](workflows/common/index-rules.md)）|
| `backlog/` | 候選池：一批一檔，整批做完移 `backlog/archive/` 凍結（[workflows/backlog.md](workflows/backlog.md)）|
| `logs/` | 歷史日誌：**已完成**事件的一句話流水帳，按月分檔 `<YYYY-MM>.md`（活狀態另記，見 [WORKFLOWS.md](WORKFLOWS.md)）|
| `{{內容真相層目錄，如 summaries/ translations/ notes/}}` | {{一件一檔的摘要／翻譯／筆記；與 `index/` 的列互指}} |
| `{{衍生層目錄，如 html/，可選}}` | {{由真相層產生的呈現頁；改產生器不改產出}} |
