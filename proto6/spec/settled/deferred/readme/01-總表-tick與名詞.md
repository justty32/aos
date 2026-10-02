← [暫緩區：之後再加的規定](../README.md)（分檔 1/3）｜[下一份](02-總表-daemon與helper.md)

## 總表

日期都是 2026-10-01。

### tick 與名詞

| 條號 | 標題 | 狀態 | 原因 | 在哪 |
|---|---|---|---|---|
| B-628 | 上下層判定：預設看資料夾包含、可登記覆蓋 | 暫緩 | 使用者：「也不需要判斷上下層」；之後由 node 模組照資料夾包含關係算 | [tick.md](../tick.md) |
| B-602（部分） | 完整互斥的其餘細節 | 暫緩 | 最簡鎖已做（拿不到回 0、鎖 fd 不傳給任務）；鎖 fd 交給任務核對、後代握鎖擋下一格、回 75 先不做 | [tick.md](../tick.md) |
| B-620（部分） | 任務的帳號（125） | 暫緩 | 使用者：「帳號不對，也不管」；核心不看 `user` | [tick.md](../tick.md) |
| B-633（部分） | 落盤、寫不進與讀不懂 | 暫緩 | 使用者：默認紀錄是好的、`--firstdo-fsync` 先不做 | [tick.md](../tick.md) |
| B-625（部分） | 加入普通設定（`aos-config-add`） | 暫緩 | 使用者 2026-10-01 第四批裁定搬暫緩區：09-29 規劃、從沒寫過程式；改 `config/` 就自己改。當機恢復、重要設定手改、恢復前驗證仍在 [tick/recovery.md](../../tick/recovery.md) | [tick.md](../tick.md) |
| P-207 | 加入普通設定（`aos-config-add` 的 argv 與結束碼） | 暫緩 | 同 B-625（部分） | [protocol/tick.md](../protocol/tick.md) |
| B-624（部分） | 發布摘要（`aos-publish`） | 暫緩 | 使用者 2026-10-01 第五批：「aos-publish我覺得要改名，我預期它的作用，就是把這一格的一些狀況總結成json檔案寫好」，討論後「那看來aos-summarize其實是暫時不需要了，拿掉。」之後若要，方向是「把這一格的狀況總結成 JSON」，名字不用 publish（會跟傳訊混）。`aos-mq post` 仍在 [tick/mq.md](../mq.md) | [tick.md](../tick.md) |
| P-206（部分） | `aos-publish` 那列 | 暫緩 | 同 B-624（部分） | [protocol/tick.md](../protocol/tick.md) |
| B-623、B-624 | 系統訊息佇列 `aos-mq get`／`aos-mq post` | 暫緩 | 使用者 2026-10-01 第十八批：「1. 都按你建議」——要靠暫緩區的 daemon 通道，用途已被 daemon 訊息模組（[B-645](../../daemon/mq.md)）取代 | [mq.md](../mq.md) |
| P-206 | `aos-mq` 的 argv 與檔案格式 | 暫緩 | 同上 | [protocol/tick.md](../protocol/tick.md) |
| B-629 | 標準任務表範本（整條） | 暫緩 | 同上：系統級任務全部暫緩，範本只剩使用者任務、現在沒有系統級任務要放 | [template.md](../template.md) |
| B-404（部分） | 清理 `aos-clean` 這項系統級任務 | 暫緩 | 同上：現在沒東西可清；B-404 原條就地標暫緩 | [base/storage.md](../../../base/storage.md) |
| B-630、B-622、B-632 | `aos-git`：開格、存檔點、收尾；git 的共同規則；沒有 git 時的下游做法 | 暫緩 | 使用者 2026-10-01 第十七批：「git這塊先不要進範本。」從沒寫過程式；改用 hooks 加普通 git 指令（B-635 範例） | [git.md](../git.md) |
| P-205 | `aos-git` 的 argv 與結束碼 | 暫緩 | 同上 | [protocol/tick.md](../protocol/tick.md) |
| B-621 | 前面的項沒跑好就停格（`aos-tick-check-task`） | 暫緩 | 使用者 2026-10-01 第十六批：「aos-tick-check-task這個先放進暫緩。」從沒寫過程式；它要建的停格檔同批改名 tasks-blocked、改了規則 | [tick.md](../tick.md) |
| P-204 | `aos-tick-check-task` 的 argv 與結束碼 | 暫緩 | 同 B-621 | [protocol/tick.md](../protocol/tick.md) |
| P-212 | `aos-as`：切換帳號 | 暫緩 | 使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」現行切帳號只在 daemon 設定檔做（帳號模組） | [protocol/tick.md](../protocol/tick.md) |
| B-634 | `aos-cg`：每項一框（連同撤回的 B-631） | 暫緩 | 使用者 2026-10-02 第二十三批：「aos-cg搬進暫緩區。」從沒寫過程式；每項一框、跑完收殘留現在由 daemon 收屍模組做（[B-644](../../daemon/cgroup.md)） | [cg.md](../cg.md) |
| P-211 | `aos-cg` 的 argv 與結束碼 | 暫緩 | 同 B-634 | [protocol/tick.md](../protocol/tick.md) |
| T-09 | 收尾、排空停機、熱重載、逃生口 | 暫緩 | 全是舊 daemon 用語，最核心 daemon 第一版不做 | [terms.md](../terms.md) |

撤回、不會回來的 tick 舊做法（沒有 `.aos/` 時交給 aos-exec 的退路、inst.json 路徑正規化、`--node` 旗標、讀表驗四件事與表壞回 2、`methods` 欄、整格回 1／2／75 的碼表、`AOS_NODE_DIR`、`AOS_TICK_RECORD`、`aos-tick` 目標給檔就拿它當任務表，以及 2026-10-01 撤回的 inst 頂層與任務表的 `user`、inst「先決定身分，切完才解析」整節）列在 [tick.md 篇末](../tick/04-已撤回與被取代.md#已撤回被取代)。
