# proto5/notes 修壞連結：另一台機器的絕對路徑 → 相對路徑

`proto5/notes` 底下多份報告是在另一台機器（`/home/guanyu/projs/aos`）產出的，內文大量連結、行內 code、純文字都寫成那台機器的絕對路徑，在這個 repo（`justty32` 這台）打開全是死路。這次把它們**只改路徑、不改文字內容**，全部換成從各自 md 檔出發的相對路徑。

## 改了什麼

共 **16 個檔、828 處**：

| 檔案 | 處數 |
|---|---:|
| 2026-09-21-inst-rev-rules.md | 4 |
| 2026-09-22-act-report-astra.md | 79 |
| 2026-09-22-daemon-kernel-report-astra.md | 204 |
| 2026-09-22-llm-cpu-report-astra.md | 177 |
| 2026-09-22-timeout-report-astra.md | 119 |
| 2026-09-23-rearch/impl-task.md | 1 |
| 2026-09-23-rearch/review-agent1-report.md | 33 |
| 2026-09-23-rearch/review-agent1-task.md | 1 |
| 2026-09-23-rearch/review1-report.md | 43 |
| 2026-09-23-rearch/review1-task.md | 1 |
| 2026-09-23-rearch/review2-report.md | 68 |
| 2026-09-23-rearch/review2-task.md | 1 |
| 2026-09-23-rearch/review3-report.md | 54 |
| 2026-09-23-rearch/review3-task.md | 1 |
| 2026-09-23-rearch/review4-report.md | 41 |
| 2026-09-23-rearch/review4-task.md | 1 |

改完 `grep -rn "/home/guanyu" proto5/notes` 為 0。

## 規則

- `/home/guanyu/projs/aos/` 對應這個 repo 根目錄。用 Python `os.path.relpath` 算出從每個 md 檔所在資料夾到目標檔的相對路徑，不手算。
- 涵蓋三種寫法：markdown 連結 `[label](/home/guanyu/.../x.py:12)`、行內 code 反引號 `` `/home/guanyu/.../x.md` ``、純文字直寫路徑；三種都改。
- 帶 `:行號` 尾巴的（例如 `:114`）保留在轉完的相對路徑後面。
- 有 7 處是「裸路徑」——只寫 `/home/guanyu/projs/aos` 本身（沒有後面的檔案路徑），用來描述「repo 在哪」而不是連到某個檔。同一條規則機械套用：換成該 md 檔到 repo 根目錄的相對路徑（例如 `proto5/notes/2026-09-23-rearch/*.md` 換成 `../../..`）。沒有另外編文字說明，因為任務要求只改路徑不改文字。
- 只改路徑本身，前後文字、連結顯示文字（`[label]` 部分）一律不動。

## 抽查結果（`test -e`）

隨機抽 10 個轉換後的連結，用 `test -e` 從各自 md 檔所在資料夾確認目標存在，全部通過：

```
proto5/notes/2026-09-22-daemon-kernel-report-astra.md   ../../proto4-3/aos_kernel.py         存在
proto5/notes/2026-09-23-rearch/review1-report.md        ../../spec/cpu.md                    存在
proto5/notes/2026-09-22-act-report-astra.md              ../lib/aos_agent.py                   存在
proto5/notes/2026-09-22-daemon-kernel-report-astra.md   ../spec/inst-posix.md                存在
proto5/notes/2026-09-22-daemon-kernel-report-astra.md   ../../proto4-3/aos_inst.py            存在
proto5/notes/2026-09-22-timeout-report-astra.md          ../lib/aos_agent.py                   存在
proto5/notes/2026-09-22-timeout-report-astra.md          ../../proto4-3/aos_daemon_entry.py    存在
proto5/notes/2026-09-22-timeout-report-astra.md          ../../proto4-5/aos_llm.py             存在
proto5/notes/2026-09-23-rearch/review3-report.md        ../../spec/cpu.md                    存在
proto5/notes/2026-09-22-llm-cpu-report-astra.md          ../../proto4-7/mailbox.py             存在
```

另外不只抽查——把改完的全部 746 個相異目標路徑都跑了一遍 `os.path.exists`（等同 `test -e`），列在下面「指不到的目標」。

## 指不到的目標（不是連結沒轉對，是目標本身在這個 repo 裡已經不在／從沒對過）

全部 8 處、3 種原因，都**保留轉換後的相對路徑原樣**，沒有亂指到別的檔：

1. **`proto5/spec/exec.md`**（共 5 處：`2026-09-22-daemon-kernel-report-astra.md` 的 `../spec/exec.md:22`、`:59`、`:63`、`:7`，`2026-09-22-timeout-report-astra.md` 的 `../spec/exec.md:42`）——這份規範後來改名成 `proto5/spec/aos-exec.md`，note 寫的時候還叫 `exec.md`。連結本身轉換沒錯，是規範檔案名字後來變了。
2. **`proto4-5/llm_cpu_module.py`**（1 處：`2026-09-22-llm-cpu-report-astra.md` 寫成 `../../protos4-5/llm_cpu_module.py:137`）——原文本身多打一個 `s`（`protos4-5` 而非 `proto4-5`），是另一台機器筆記原有的手誤，不屬於本次要改的絕對路徑問題，所以沒有動它（只改路徑格式，不改文字內容）。
3. **`proto5/backlog/cpu-simpler.md`、`proto5/backlog/kill-tree-exceptions.md`**（各 1 處，都在 `2026-09-23-rearch/review1-report.md`）——`git log --all --diff-filter=D` 查得到這兩份確實曾經存在於 `proto5/backlog/`、後來被刪除，屬於任務描述的「另一台機器上有、這裡已刪」情形。
