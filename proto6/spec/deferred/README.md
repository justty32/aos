# 暫緩區：之後再加的規定

← [整理區](../README.md)｜[慣例](../conventions.md)｜[通用 tick](../tick.md)｜[daemon](../daemon/README.md)

## 這是什麼

**這裡放「已經想好、但現在先不做」的規定。** 2026-10-01 使用者把 Python POC 定成「默認一切正常、先不考慮邊緣狀況」，又把 daemon 砍成只定期叫 `aos-exec` 的最核心版本。原本寫好的完整互斥、上下層判定、任務帳號檢查、落盤保證，以及整套舊 daemon（登記、runner、收尾、通道、熱重載、helper、cgroup、訊息）都還沒要做，但也不刪，就搬到這裡。

- **條號保留、不重用。** 以後加回來時沿用原號；新規定另開新號。
- **每條標題正下方有一行狀態**，三種之一：
  - **暫緩**：之後可能照原文（或改寫後）加回來。
  - **已被 X 取代**：同一件事新設計已經換了做法，原文只留作紀錄，不會照原樣回來。
  - **部分已被取代、其餘暫緩**：兩種混在一條裡，狀態行寫明哪部分被誰取代。
- **原文照 2026-09-30 的樣子留著。** 裡面的結束碼（75、2、整格回 1）、`node` 用語（tick 層現在叫工作資料夾〔使用者 2026-10-01〕；講上下層的「上層 node／下層 node」照留）、「本篇是正本」之類的話都是舊設計當時的寫法；加回來時要照 [C-08](../conventions.md) 重定碼、照 [C-09](../conventions.md) 換狀態資料夾名。
- **部分暫緩的條**：原條還在正式篇，暫緩的那段在這裡用「暫緩：B-xxx …」當標題。

## 檔案

| 檔 | 內容 |
|---|---|
| [tick.md](tick.md) | B-628 上下層判定（整條）；B-621 `aos-tick-check-task`（整條，第十六批）；B-602、B-620、B-624、B-625、B-633 的暫緩部分；篇末「已撤回／被取代」 |
| [protocol/tick.md](protocol/tick.md) | tick 協議先不做的條：P-207 `aos-config-add` 的格式；P-206 的 `aos-publish` 那列；P-212 `aos-as`；P-204 `aos-tick-check-task`（第十六批）；P-205 `aos-git`（第十七批）；P-206 `aos-mq`（第十八批）；P-211 `aos-cg`（第二十三批） |
| [terms.md](terms.md) | T-09 收尾、排空停機、熱重載、逃生口（舊 daemon 用語） |
| [helper.md](helper.md) | B-303 可選 root helper 與 `aos-as` |
| [cg.md](cg.md) | B-634 `aos-cg` 每項一框、B-631（撤）cgroup 框的備援（整篇，第二十三批，原 `tick/cg.md`） |
| [git.md](git.md) | B-630、B-622、B-632 `aos-git` 與 git 規則（整篇，第十七批，原 `tick/git.md`） |
| [mq.md](mq.md) | B-623、B-624 系統訊息佇列（整篇，第十八批，原 `tick/mq.md`） |
| [template.md](template.md) | B-629 標準任務表範本（整篇，第十八批，原 `tick/template.md`；含第十七批的有 git 版） |
| [daemon/](daemon/README.md) | 舊 daemon 設計各條（B-504、B-601、B-603～615）與 systemd 範例 |
| [protocol/daemon/](protocol/daemon/README.md) | 舊 daemon 協議 P-101～119（P-100 除外，改寫後留在正式篇） |

## 分檔目錄

> 2026-10-02 整理：原檔約 17 KB 超過 8 KB 門檻，按標題逐字拆進 `readme/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-總表-tick與名詞.md](readme/01-總表-tick與名詞.md) | 總表 |
| 2 | [02-總表-daemon與helper.md](readme/02-總表-daemon與helper.md) | daemon 與 helper |
| 3 | [03-總表-daemon協議與其他.md](readme/03-總表-daemon協議與其他.md) | daemon 協議；區外暫緩的段落；已知的設計問題（記錄，這輪不改） |
