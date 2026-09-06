# kids 工具包

生小孩，也看小孩走到哪。

| 工具 | 做什麼 |
|---|---|
| `spawn(name, persona, clock?, template?)` | 建一個子 agent。 |
| `kids_list()` | 讀 `kids.json`，列出小孩的狀態。 |

小孩住在 `<home>/kids/<名字>/`。它自己就是完整世界。人格由 `persona` 給。它跟父共用同一個 LLM 資料夾。

`clock=shared` 會把小孩掛到父的 `.aos/inst`。父走一格，小孩也走一格。`clock=own` 會向 daemon 要自己的鐘。沒設 `AOS_DAEMON_DIR` 時只建資料夾。

spawn 會寫三種關係資料：

- 小孩的 `parent.json`。
- 父子雙方的 `contacts.json`。
- 父的 `kids.json`。

`template` 可填 `proto2/templates/<名字>/` 的名字。模板存在時先鋪設定，再由 persona、父的 packs 與共用 LLM 蓋上去。模板目錄不存在也照常建立。
