# Deliver 的介面與契約

> **以下是風格模擬，不是本人的意見。**

| 項目 | 內容 |
|---|---|
| 題目 | Deliver 的介面與契約（對到 OPEN-QUESTIONS 第 7、8、9 題） |
| 開場日期 | 2026-08-26 |
| 環境 | 原生 Linux（Manjaro，不是 WSL）；codex 0.149.1；`-s workspace-write`；無網路；四位平行；單輪逾時 1800 秒 |
| reasoning effort | `high` |
| 評委 | Leslie Lamport persona |
| 狀態 | 第 2 輪已完成，共三輪 |

| 參賽者 | persona | 場地 | codex thread id（續輪 resume 用） |
|---|---|---|---|
| p1 | Rob Pike | `~/aos-hack/deliver-contract/p1` | `01a03e24-2e95-7640-b64c-99d5a6648d6f` |
| p2 | Rich Hickey | `~/aos-hack/deliver-contract/p2` | `01a03e24-310d-7413-bebf-109eb39a8c70` |
| p3 | Bryan Cantrill | `~/aos-hack/deliver-contract/p3` | `01a03e24-2eeb-7750-8fe8-7ced989b0848` |
| p4 | Julia Evans | `~/aos-hack/deliver-contract/p4` | `01a03e24-31d4-7d53-af4e-ee6ca3cbbdb3` |

## 分檔目錄

> 2026-09-25 整理：原檔 84 KB 超過門檻，按標題逐字拆進 [`deliver-contract/`](deliver-contract/01-第-1-輪紀錄.md)；本檔只留前言與目錄（原路徑保留當入口）。

| # | 檔 | 段落 | 大小 |
|---|---|---|---|
| 1 | [01-第-1-輪紀錄.md](deliver-contract/01-第-1-輪紀錄.md) | 第 1 輪紀錄 | 7.1 KB |
| 2 | [02-3-好處壞處.md](deliver-contract/02-3-好處壞處.md) | 第 1 輪紀錄 ＞ 3. 好處／壞處 | 2.4 KB |
| 3 | [03-4-題目那三個數字.md](deliver-contract/03-4-題目那三個數字.md) | 第 1 輪紀錄 ＞ 4. 題目那三個數字 | 7.0 KB |
| 4 | [04-第-1-輪評分與意見.md](deliver-contract/04-第-1-輪評分與意見.md) | 第 1 輪評分與意見 | 6.5 KB |
| 5 | [05-下一輪的資料包.md](deliver-contract/05-下一輪的資料包.md) | 下一輪的資料包 | 5.8 KB |
| 6 | [06-3-兄弟專案裡可以抄的.md](deliver-contract/06-3-兄弟專案裡可以抄的.md) | 下一輪的資料包 ＞ 3. 兄弟專案裡可以抄的 | 5.5 KB |
| 7 | [07-第-1-輪白話導讀.md](deliver-contract/07-第-1-輪白話導讀.md) | 第 1 輪白話導讀 | 5.4 KB |
| 8 | [08-第-2-輪紀錄.md](deliver-contract/08-第-2-輪紀錄.md) | 第 2 輪紀錄 | 3.2 KB |
| 9 | [09-2-坑的總表.md](deliver-contract/09-2-坑的總表.md) | 第 2 輪紀錄 ＞ 2. 坑的總表 | 6.7 KB |
| 10 | [10-3-好處壞處.md](deliver-contract/10-3-好處壞處.md) | 第 2 輪紀錄 ＞ 3. 好處／壞處 | 7.0 KB |
| 11 | [11-5-仍然不知道的.md](deliver-contract/11-5-仍然不知道的.md) | 第 2 輪紀錄 ＞ 5. 仍然不知道的 | 2.5 KB |
| 12 | [12-第-2-輪評分與意見.md](deliver-contract/12-第-2-輪評分與意見.md) | 第 2 輪評分與意見 | 6.7 KB |
| 13 | [13-下一輪的資料包.md](deliver-contract/13-下一輪的資料包.md) | 下一輪的資料包 | 5.6 KB |
| 14 | [14-3-兄弟專案裡可以抄的.md](deliver-contract/14-3-兄弟專案裡可以抄的.md) | 下一輪的資料包 ＞ 3. 兄弟專案裡可以抄的 | 5.2 KB |
| 15 | [15-第-2-輪白話導讀.md](deliver-contract/15-第-2-輪白話導讀.md) | 第 2 輪白話導讀 | 6.2 KB |
