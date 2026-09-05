> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# fuse-host-why：最初只是想少碰磁碟

← [ideas](README.md)｜[fuse-host](fuse-host.md)｜[fuse-host-doorman](fuse-host-doorman.md)｜[fuse-host-impl](fuse-host-impl.md)｜[top-to-bottom/01-top](top-to-bottom/01-top.md)

本檔是 fuse-host 三篇的前情補述：回頭拆開「當初為什麼想到 FUSE」。**本檔無裁決**，只把
兩個原本混在一起的需求分開，讓玩的順序更便宜、更容易看懂。

## 使用者原話（2026-09-04）

> 然後fuse這邊我其實最開始的對它的用途的規劃，就只是覺得檔案系統要頻繁存取磁碟不太好，所以想說用fuse，在記憶體中做操作。後來說這個方式有好處在於一些特定操作會被fuse偵測到，並做出一些額外動作

## AI 觀察（非裁決，可否決）

### a. 昨天把兩個需求混在一起了

1. 不想頻繁碰磁碟，希望操作待在記憶體。
2. 希望特定檔案操作能被看見，接著做記帳、拒絕或別的額外動作。

第一題先是 tmpfs；第二題才要在 inotify 與 FUSE 之間選。

### b. 需求一的直接答案是 tmpfs，不是 FUSE

**tmpfs 就是一個住在記憶體裡的目錄，核心已經做好，aos 零程式碼。** 把 `.aos/` 放上去，
平常的讀、寫、`rename` 都還是普通檔案操作。

反直覺的是：**FUSE 比 tmpfs 慢。** 每次讀寫都得走「核心 → 使用者寫的 FUSE 程式 → 核心」；
即使資料最後也放在記憶體，仍多了這兩趟。若最初動機是速度，先寫 FUSE 反而走反方向。

Linux 的普通磁碟檔案也不是每次 `write` 都立刻碰硬碟：內容先進頁快取，核心之後慢慢刷下去。
真正會逼它當場等磁碟的是 `fsync`／`fdatasync` 這類同步。所以第一步應先查 aos 是否到處
`fsync`；本次盤點結果是**沒有**，大部分寫入本來就先落在記憶體。

可預測性仍有差：普通檔案的頁快取何時刷下去不是 aos 控制的；tmpfs 永遠在記憶體，時間比較
穩。代價則是斷電或重開機就全沒了。

這個代價剛好對得上 2026-09-03 的裁決：**原稿在頂層給人，`.aos/` 是機器產物。** 因此可以
讓原稿留在磁碟、只把 `.aos/` 放 tmpfs；需要時由 loader 再從原稿生回機器狀態。

### c. 需求二分三級

| 想做什麼 | 先用什麼 | 原因 |
|---|---|---|
| 只想知道發生什麼、做記帳 | **inotify** | 不接管檔案系統，只收 Linux 變更通知，幾十行即可 |
| 想拒絕非 aos 程式寫 `.aos/` | **FUSE** | 必須站在操作途中，才有機會回答「不行」 |
| 想演出根本不存在的假檔案，像 `/proc` | **FUSE** | 檔案內容要由使用者程式現場回答 |

「門鈴太密」與半成品被提早端走的問題（[fuse-host §c](fuse-host.md#c-這改的不是概念是兩個格子的底座)、
[doorman](fuse-host-doorman.md)）只在接管層級出現。只用 inotify 記帳時，檔案操作仍由原本的
檔案系統完成，通知不必直接推動 aos 回合。

### d. 建議玩的順序

**tmpfs 先**（零成本，直接解需求一）→ 真想記帳再加 **inotify** → 真要擋寫入或生假檔案，
才寫 **FUSE**。第一步不用寫程式，第二步也不用自己寫檔案系統，正合「先玩再設計」的裁決。

[fuse-host](fuse-host.md)、[doorman](fuse-host-doorman.md)、[impl](fuse-host-impl.md) 三篇不用改寫；
它們談的是 FUSE 真上場後的形狀，本檔只把最初動機拆開。

## 現有 aos 對照

以下數字取自程式碼路徑，並用現有 `build/bin/aos` 跑一個受控例子：一筆
`sh -c 'printf hello'`，`aos run --step 1`。

| 問題 | 現況 |
|---|---|
| 有沒有同步落盤 | **沒有** `fsync`、`fdatasync`、`O_SYNC`／`O_DSYNC` 或同類呼叫。`fflush`、close、原子 `rename` 只把資料交給核心，不保證落盤 |
| 一個有工作的一回合寫多少 | 對 `N` 筆 inst：`state.json` 寫 2 次、`out/` 寫 `N` 份、`turn` 寫 1 次；另有每筆 inst 的 stdin／stdout／stderr 3 個 `/tmp` 暫存檔，收完即刪。受控的 `N=1` 最後新增／更新 4 個持久檔：`state.json` 243 B、outcome 188 B、`turn` 2 B、空的 `run.lock` 0 B；既有 inbox 109 B 只是 `rename` 成 batch inst。內容大小隨 argv、輸出、時間字串與 agent 狀態變動 |
| 空回合寫多少 | `state.json` 1 次、`turn` 1 次；不建 batch／out，也沒有 exec 暫存檔 |
| `.aos/` 能否整棵放 tmpfs | **現有四個 core 可以。** loop 的暫存檔都在目標旁，inbox → batch 的 `rename` 兩端也都在 `.aos/`；沒有把頂層原稿直接 `rename` 進 `.aos/`。用掛載或讓 `.aos` symlink 指到 tmpfs，不會讓這些 rename 跨檔案系統。未來 loader 若想用 `rename(頂層原稿, .aos/…)` 就會遇到 `EXDEV`，應改成讀／寫或 copy |
| `series.json` | `core/wire`、`loop`、`exec`、`tick` 都沒有寫它；今天尚未實作 |
| `run.pid` | 只有 `--step 0`／daemon 才寫；`--step 1` 不寫 |

若有到期的 every，loop 還會寫 batch inst（同一路徑先寫原文、再寫正規化 JSON）與 `.last`；
若 inst 本身是 `aos tick`，tick 可能再寫 routines、schedule、inbox／agent 訊息與追加 log。那不是
每回合固定量，所以不塞進上面的典型 `N=1` 數字。

## 相關清單

- `G14`（載入器）：原稿在磁碟、`.aos/` 在 tmpfs 的前提，是 loader 能重建機器產物。
- `G18`（成本）：先用零程式碼的 tmpfs，避免為錯的速度假設先付 FUSE 實作成本。
- `G19`（不可靠與可預測性）：頁快取刷盤時間不受控；tmpfs 的時間較穩，但重開即失憶。
- `G03`（命名空間／掛載）：把 `.aos/` 掛到 tmpfs，就是明說的一個掛載邊界。
- `G07`（程式／行程分界）：原稿仍是穩態，tmpfs 裡是可重建的執行狀態。

續篇：[fuse-host-extras](fuse-host-extras.md)——門房偵測到操作後，額外處理可能有哪些。
