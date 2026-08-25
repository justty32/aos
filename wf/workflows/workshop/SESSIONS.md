# 研討會的 codex session 一覽

← [workshop](README.md)｜[紀錄](records/)｜[待答問題](OPEN-QUESTIONS.md)

2026-08-25 這一天所有 `codex exec` session 的 id。**要接回同一個人格、同一份記憶，
就用這些 id `resume`。**

## 先看這三件事，不然你會撲空

1. **它們已經 archive 了。** 使用者在收場時要求「讓所有 codex 做 compact」——
   **codex CLI 沒有 compact 指令**（`codex help` 裡只有 `archive`／`unarchive`），
   所以做的是 archive。**resume 之前要先 unarchive：**

   ```bash
   codex unarchive <id>
   codex exec resume <id> - < 任務書.md
   ```

2. **session 檔是機器本地的。** 存在 `~/.codex/sessions/<年>/<月>/<日>/`
   （Windows 的 codex 與 WSL 裡的 codex **各存各的，互不相通**）。
   **這一天的 session 全部在公司那台 Windows**（外加一個在該機的 WSL Ubuntu）。
   **在家裡那台是接不到的**——除非把對應的 `rollout-*.jsonl` 檔複製過去。
   接不到就當作重新開場：把紀錄檔當想法池寫進任務書，參與者照樣接得住
   （[README 的〈角色〉](README.md)有寫這個退路）。

3. **`codex exec resume` 不吃 `-s`、`-C`、`--add-dir`**（沙盒與工作目錄從原 session 繼承），
   帶了會直接 usage error 退出碼 2。`--json`／`-o`／`-c` 照常。
   事件裡的欄位是 **`thread_id`**，不是 `session_id`。

## 第一批參與者（Windows codex）

只參加了**〈核心行程、子行程，與外部處理器的契約〉**那一場（R1、R2）。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03653-61a9-7f21-9615-6c2921f1ead6` |
| 資深架構師 | `01a0364d-b8e1-7113-af65-bdf892bb14ef` |
| 資深研究人員（作業系統／體系結構） | `01a0364f-6a54-7713-844e-dfd70278cbe0` |
| 要接這個工具的開發者 | `01a03651-d860-74d0-ae5e-22d83cc959d3` |

## 第二批參與者（Windows codex）——**脈絡最厚的一批**

同樣四種身份，但是**不同的人**。他們一路參加了**六場**：
四個懸而未決的選擇（R1、R2）→ agent loop 架構（R1、R2 收攏）→ 回頭審視 →
隨意發想 → 用 aos 實現 workflows → 跟現有工具協作（含追問輪）→ 最後總結。

**要續談 aos 的設計，接這一批。**

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（作業系統／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

> 最後總結那一輪的任務書明講「**這是你最後一次發言**」，所以再 resume 他們的話，
> 要在任務書裡說清楚「研討會重開了」，否則他們會以為自己已經下班。

## 工具人（Windows codex）

| 角色 | session id | 他手上有什麼 |
|---|---|---|
| **書記** | `01a0368f-1582-7100-b254-5d6fd9a4cd15` | 寫過全部七份紀錄，context 很厚也很慢——**重開新的可能比 resume 快** |
| **祕書** | `01a037a6-8434-7fe0-9a0b-d5ebc2dd02ca` | 寫了 `BACKGROUND.md` 與拆檔後的 `background/` 17 檔 |
| **問題彙整** | `01a0379d-9ee6-7a92-bc88-7fb387f4366b` | 讀七份紀錄產出 `OPEN-QUESTIONS.md`（新開的 session，不是書記本人） |

## 實測（**WSL Ubuntu 裡的 codex，不是 Windows 那支**）

| 任務 | session id |
|---|---|
| T5 agent loop 實測（[紀錄](../experiments/t5-agent-loop.md)） | `01a037cd-feac-74a0-a881-8249e3ab858e` |

要 resume 它得進 WSL：

```bash
wsl -d Ubuntu -e bash -lc 'codex unarchive 01a037cd-feac-74a0-a881-8249e3ab858e'
```

> 這一趟裡 vcpkg configure 被沙盒的唯讀檔案系統擋住（`take_exclusive_file_lock` 失敗），
> 所以用的是既有的 `build/bin/aos`。真模型三支都沒跑通：codex 被沙盒唯讀擋在初始化、
> Claude 的 OAuth 過期、WSL 裡沒裝 pi。**下次補實測要先解掉這三件。**
