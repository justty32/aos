← [proto5 README](../../README.md)｜報告：[notes/2026-09-25-arknights/team/](../../notes/2026-09-25-arknights/team/README.md)｜教程：[08 團隊](../../tutorials/08-team.md)

# arknights 補人物隊（強模型版，2026-09-25）

拿 proto5 的團隊去做真實專案 `~/repo/narratives/arknights`（《明日方舟》全劇透設定集）的主業：**補次要人物**——
讀別人寫好的草稿、逐句回原文核對、寫成正式詞條＋證據檔、超過 5KB 拆檔、回填導航表與索引計數。

| 檔 | 是什麼 |
|---|---|
| `team.json` | 名冊：領隊 `lead`、寫手 `writer-1`／`writer-2`、審查員 `reviewer`，全用 `gpt-6-astra`；corpus 唯讀掛載；不准生新成員；`cmd_ok` 只放專案的三支檢查腳本 |
| `templates/lead`、`writer`、`reviewer` | 自訂模板：人格（`system.md`，專案規矩從 arknights 的 CLAUDE.md／workflows 抄）＋ `llm.params.max_tokens` 32000、逾時 10 分 |
| `routes.json` | 門房：「補人物 X」直接開單給 `writer-1`（不叫領隊），驗收 12 條寫死；「補一批人物：A、B、C」沒規則，落穿給領隊拆 |
| `llm.json` | LiteLLM `localhost:4000` 上的代號：`gpt-6-astra`（＋`-low/-medium/-high`）、`claude-opus-5`、`claude-sonnet-5`、`claude-haiku-4.5`、`deepseek-chat`（降級用，先登記） |
| `run.py` | 一次試跑：開機（帶 `AOS_HOPS`）→ 專案副本退回基線 → 重建團隊 → 丟一句話 → 等單子結束 → 紀錄寫進 `<專案>/aos-runs/<時間>-<one|batch>/` |

## 先準備專案副本（絕不在本尊上跑）

```sh
git -C ~/repo/narratives/arknights worktree add ~/tmp/arknights-try -b aos-try HEAD
ln -s ~/repo/narratives/arknights/corpus ~/tmp/arknights-corpus
ln -s ../../arknights-corpus/raw       ~/tmp/arknights-try/corpus/raw
ln -s ../../arknights-corpus/extracted ~/tmp/arknights-try/corpus/extracted
```

- corpus 用**相對**符號連結：主機上 `~/tmp/arknights-try/corpus/raw` → `~/tmp/arknights-corpus/raw`；牢裡專案是 `/work/ws`、corpus 掛在 `/work/arknights-corpus`（名冊的唯讀掛載），同一條 `../../arknights-corpus/raw` 也解得開。絕對連結在牢裡會斷。
- 草稿（本尊工作樹裡沒追蹤的檔）只複製、不動本尊：`aos-drafts/<名>/詞條草稿.md`、`證據草稿.md`。
- 本尊 HEAD 有 7 條斷鏈（已 commit 的檔連到沒 commit 的草稿），副本上補一個「aos 試跑基線」commit 把那 5 個檔帶進來，`check_links.py lore` 才會是 0。`run.py` 每次都退回這個 commit。

## 跑

```sh
python3 proto5/examples/arknights/run.py one 老何塞
python3 proto5/examples/arknights/run.py batch 老木頭 老薑 老財
python3 proto5/examples/arknights/run.py stop
```

跑的中途想看：`. ~/tmp/arknights-aos/env.sh; aos-team mail`、`aos-team task ls --all`；寫手問人：`aos-team wait ls`、`aos-team answer q-0001 "…"`。

## 換成本尊（還沒做，要使用者點頭）

- `team.json` 的 `"project": "~/tmp/arknights-try"` 改成 `"~/repo/narratives/arknights"`；corpus 就在專案裡，名冊三個成員的 `mounts` 整段拿掉。
- `cmd_ok` 白名單裡的人名換成這一批要補的人（白名單要整串相等，人名寫在指令裡）。
- 本尊工作樹有 140 多個沒追蹤的草稿，寫手會直接改到 `lore/`；commit 仍然留給人（`git add` 只加明列的人物與索引檔，嚴禁 `git add -A`）。
