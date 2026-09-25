# examples/commons — 兩支做事的隊＋一支圖書館員隊

← [proto5 README](../../README.md)｜規格 [spec/team/commons.md](../../spec/team/commons.md)｜報告 [notes/2026-09-25-commons](../../notes/2026-09-25-commons/README.md)

09-25 真跑用的三份名冊（`aos-team init --config <檔> --target <隊>`）。三支隊的資料夾放在同一個上層，就共用上層的 `commons/`：

```text
<上層>/
  commons/          aos-team init 建；只有圖書館員隊寫
  ta/  team.json ← team-a.json      投稿的隊（一個領隊就夠）
  tb/  team.json ← team-b.json      查閱、用在自己單子上的隊（領隊＋工人）
  lib/ team.json ← librarian.json   圖書館員隊（一個成員）
  p-a/ p-b/ p-lib/                  三個專案（圖書館員的專案是空的，名冊一定要有 project）
```

| 檔 | 誰 | 模型 | 為什麼這樣編 |
|---|---|---|---|
| [team-a.json](team-a.json) | `lead-a`（領隊） | `astra` | 投稿只要讀檔＋`commons_submit`，領隊的工具就夠，不用工人 |
| [team-b.json](team-b.json) | `lead-b`＋`worker-b` | `astra` | 領隊 `commons_search` 查到後寫進單子的 facts，工人照著寫檔並引用條目 id |
| [librarian.json](librarian.json) | `librarian`（模板 `librarian`） | `default`（便宜的，例：`deepseek-chat`） | 正式員工：常駐、服務所有隊；幾乎全是郵差機械做，模型只判「像既有條目」的投稿 |

- `model` 是 `llm.json` 的代號：這次 `default`＝LiteLLM `deepseek-chat`、`astra`＝LiteLLM `chatgpt-gpt-6-astra`。
- 同一個 kernel 上成員名不能重複（kernel 用 `agent-<名>` 登記），所以三隊的人都取不同名字。
- 不想讓某隊看 commons：名冊頂層加 `"commons": false`。
