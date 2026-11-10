# 清道夫 proc（stderr 封存＋保留期＋收表外子 loop）（11-10）

← [11-10](../)｜同日另一條線：[prefix-fixes](../prefix-fixes/)（設計-34「daemon 端截 stderr」改由這條線處理，線 4 不做）

| 檔 | 內容 |
|---|---|
| [01-設計](01-設計.md) | 規劃員草稿照使用者裁定修訂後的定稿：形狀、封存、保留期、收殭屍的認法、鎖、報告、邊緣表 |
| [02-施工結果](02-施工結果.md) | 做了什麼、commit、怎麼驗（單元測試、/tmp 假腦三層、實跑數字）、代定表、沒做的與之後可加 |

使用說明在 [cmd/aos-sweeper/README](../../../../cmd/aos-sweeper/README.md)。

## 使用者原文

> 1. 錯誤記錄檔...我記得那是daemon轄下的procs那邊的東西。幫我做一個daemon的常駐loop proc，類似clock那樣，每十分鐘跑一次，對各種東西進行清理與封存。stderr就是封存，封存後的是git ignore。然後我記得daemon-ctl有一個指令是進行清理，沒有的話做一個，就是把這些封存的一次清掉。

> 那個常駐proc，有點類似清道夫，清理與封存的同時，也會看到那些殭屍行程，會幫忙清掉。然後daemon ctl的指令...兩個吧，一個是主動叫一次清道夫，另一個是把封存的東西刪除。也可以合併，弄成--purge

> 殭屍行程，只是想到了linux proc

> 好。不要因為太敢就省略東西，時間沒有緊急到那樣。

用法背景（同日）：

> 我要拿aos去做知識庫運用，並且要長時間做事，應該會大量使用eca。
> 主要包claude。然後會搭配一些loop fsm agent，接llm endpoint的。兩台都會要。
> 會頻繁遷移，透過github
> 所以就請盡量支援相對路徑...

## 使用者裁定（11-10 快裁，大修時可重看）

> 1.按照推薦。然後prune的功能如果被完全覆蓋了，那就刪除，或整合進指令。2.每個daemon要掛就自己掛，只管自己。3.A 4.A 5.A,但是_sweeper這個proc可以有選項，選擇retention期限，默認七天

> 因為是快速抉擇，主要靠直覺，其中可能有些錯誤，但沒關係，大修的時候再來處理

讀法（頂層轉達，照做）：

1. 名字：表上 `_sweeper`、程式 `aos-sweeper`、指令 `aos-daemon-ctl sweep`。`prune` 清的是表上久沒動的 stopped／sleeping 列，清道夫**沒有覆蓋**它 → **prune 原樣保留**。
2. 每台 daemon 自己掛、只管自己：清道夫只處理自己那台表上的零件與那台的 stack，**不往子 daemon 底下遞迴**；子 daemon 那一列本身的 stderr 歸父的清道夫。沒掛的 daemon 沒人清（使用者接受）。`aos-daemon-ctl sweep` 同理只掃目標那台。
3. 殭屍＝草稿題 2 的 A：只收有十足把握的那類（預設小格裡、表上沒有、自己的窗證明活著且是這台生的），先寫 ctl stop，之後的輪還在才 TERM→KILL；真 zombie 與認不出的只報；daemon 不在不碰任何行程。N-17「只有 daemon 碰 pid」的第二個例外。
4. 指令＝一個：`aos-daemon-ctl sweep [--dry-run]` 立刻跑一輪；`sweep --purge` 刪封存（也吃 `--dry-run`）；指令自己跑同一套程式碼、flock 錯開；常駐列 pause／stopped／沒掛照跑。
5. 封存保留期：`_sweeper` 有 retention 選項、預設 7 天、可設永不自動刪（`--retention-days none`）；argv 旗標、不加環境變數、不改 daemon.json 格式。`sweep --purge` 不管保留期全刪。報告寫封存總量。

## 結論

- 新程式 `aos-sweeper`（`cmd/aos-sweeper/bin/`）＋本體 `py/aos_sweep.py`、`py/aos_sweep_proc.py`；`aos-daemon-ctl sweep` import 同一份。daemon 程式完全不認它。
- 範本 daemon 預設都帶 `_sweeper` 一列（頂層代定，不要就刪），列上只靠 PATH 與 `$AOS_STACK`，沒有機器位置。
- 清道夫寫的東西全部不進 image（`stderr_archives/`、`sweeper_report.json`、`.sweeper.lock`、`.sweeper_pending.json`）。
- 細節與代定在 [01](01-設計.md)、[02](02-施工結果.md)。
