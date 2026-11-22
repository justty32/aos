# 前端大修：全景頁剩的、later-1115 的前端那半、拆 aos-frontend 併成一條；11-22 上層改成只信紀錄、拿掉寫死路徑（f3e2581d7），aos-eca-frontend 改不改名、大修要不要整個交給它還沒答

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

## 11-22 傍晚的現況（線 progress-1122-sweep 對 commit 補的）

- 已做：全景頁的上層只信紀錄（daemon 的 subagent 紀錄＋隊長的 `aide.json`），設定檔 `parents`、名字前綴、`parent_rules` 三種猜法拿掉，沒紀錄的平鋪在最上層；寫死的 `repo-aos`（init 預設規則、下令預設收件人）拿掉；`VIEW_TOOLS` 寫死 `~/aos-home/ws/tools` 拿掉，`aos-user` 改成 `VIEW_TOOLS` 或 PATH 上找（`f3e2581d7`，線 aos-eca-frontend-1122-parents-b，使用者 11-22「我人還在外面玩，總之先按推薦做」）。`aos-frontend.service` 的 `AOS_DAEMON` 改指 `_stack`（`a7d3e1442`）。
- 下面原文裡因此過時的兩句：「`frontend/bin/aos-frontend` 仍寫死 `~/aos-home/ws/tools`（`VIEW_TOOLS`），改讀設定沒做」已做；三個小毛病裡的「前端去活樹找 aos-user」改成照 PATH 找，但家機 PATH 上還沒有 `aos-user`（11-22 `which aos-user` 找不到；`e27106c40` 也記「家機沒有 aos-user」），所以頁上「要決定」那欄、回專區信照舊不能用。**11-22 搬好**：aos-user 放進 `proto8/frontend/aos-user/`，`proto8/frontend/bin/aos-user` 連過去，`source env.sh` 就在 PATH 上（線 aos-user-home-1122-build，跟這句同一個 commit；乾淨複本上假題目 `/api/asks` 讀得到）；「前端去活樹找 aos-user」「『要決定』那欄是空的」這兩句，**重起全景頁後生效**（新殼先 `command -v aos-user`）。
- 活的全景頁（pid 9460）還是舊程式，使用者重開 `aos-frontend serve` 才用上新版（HANDOFF，`847b38c28`）。
- 還沒做：`run_json` 丟掉子程式 stderr（`f3e2581d7` 沒碰）；其餘照下面原文。
- `aos-eca-frontend` 11-22 已領過一件真工作（上面那件）；改不改名成 `eca-aos-frontend`、前端大修要不要整個交給它，使用者還沒答。

## 全景頁剩的（overview-page 原文，逐字）

地圖方向鍵、Ctrl+K 原始碼已做（`06cf02300`）；P5 文字、按鈕字「（排隊中）」核不到：網頁 `dist/` 11-17 起不進 git，要有 Node 的機器重建一次看（原始碼 `ui/v2/src/inspector/ReadButtons.tsx` 仍有「（排隊中）」那格）；沒驗 /context 真畫面、Firefox、手機單欄等（要活樹與使用者）；`frontend/bin/aos-frontend` 仍寫死 `~/aos-home/ws/tools`（`VIEW_TOOLS`），改讀設定沒做，跟前端大修一起；前端三個小毛病（`8e0cf5caa` 回報：起前端要自設 AOS_DAEMON 否則錯誤訊息不清、前端去活樹找 aos-user、首頁 / 轉到已刪 v1 的路徑）使用者 11-18 晚：「前端的三個小毛病這塊都還好，，先留着。」→ 先留著不修；11-21 線 top-1121-frontend 乾淨複本試跑全過（hook 新格式沒弄壞前端；修寄信給沒信箱的 agent 失敗），網頁 dist/ 已 build 在工作樹 ui/v2/dist/（P5 那格字在 build 裡有，畫面沒核）；活樹 ~/aos-home 已沒有 ws/，頁上「要決定」那欄是空的、回專區信不能用；大修盤點 14 項在 frontend-備妥-1121；11-21 夜 eca-aos 讀 frontend/bin/aos-frontend 看到：run_json 丟掉子程式的 stderr，失敗只剩「aos-agent ctl ls --json failed」看不出原因（使用者「兩個都記下來」）

## 併進來的（11-22 整理，照 progress 整理報告組 2）

- later-1115「11-15 意見裡「之後再說」的」原文（逐字）：stack 遷移、aos-frontend 大修（使用者 11-17：之後整個大修大重構；環境變數名、`API.md` 還沒跟著改名——11-18 查仍是 `VIEW_*`、`view-api/0`）、systemd 規則、全景頁為何常掛
  - 其中「stack 遷移」已被 11-22 的 `_stack` 規劃與線 1～6、9 蓋過；其餘（aos-frontend 大修、`VIEW_*` 改名、systemd 規則、全景頁為何常掛）歸這條。
- refactor-tidy-inventory 剩的「拆 aos-frontend（前端先不動，等大修）」。
- 整理報告：搬家後 `~/aos-home` 只剩 llm，`VIEW_TOOLS` 寫死 `~/aos-home/ws/tools` 會更不對；`aos-eca-frontend` 掛著沒事，名字與職責還沒答。
- 同一件、沒併的：waiting-1121 第 7 項（大修盤點 14 項，在 frontend-備妥-1121），那條屬等使用者回答，不動。
