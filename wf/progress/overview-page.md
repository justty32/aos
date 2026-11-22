# 前端大修：全景頁剩的、later-1115 的前端那半、拆 aos-frontend 併成一條；名字與職責、要不要派 aos-eca-frontend 還沒答

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

## 全景頁剩的（overview-page 原文，逐字）

地圖方向鍵、Ctrl+K 原始碼已做（`06cf02300`）；P5 文字、按鈕字「（排隊中）」核不到：網頁 `dist/` 11-17 起不進 git，要有 Node 的機器重建一次看（原始碼 `ui/v2/src/inspector/ReadButtons.tsx` 仍有「（排隊中）」那格）；沒驗 /context 真畫面、Firefox、手機單欄等（要活樹與使用者）；`frontend/bin/aos-frontend` 仍寫死 `~/aos-home/ws/tools`（`VIEW_TOOLS`），改讀設定沒做，跟前端大修一起；前端三個小毛病（`8e0cf5caa` 回報：起前端要自設 AOS_DAEMON 否則錯誤訊息不清、前端去活樹找 aos-user、首頁 / 轉到已刪 v1 的路徑）使用者 11-18 晚：「前端的三個小毛病這塊都還好，，先留着。」→ 先留著不修；11-21 線 top-1121-frontend 乾淨複本試跑全過（hook 新格式沒弄壞前端；修寄信給沒信箱的 agent 失敗），網頁 dist/ 已 build 在工作樹 ui/v2/dist/（P5 那格字在 build 裡有，畫面沒核）；活樹 ~/aos-home 已沒有 ws/，頁上「要決定」那欄是空的、回專區信不能用；大修盤點 14 項在 frontend-備妥-1121；11-21 夜 eca-aos 讀 frontend/bin/aos-frontend 看到：run_json 丟掉子程式的 stderr，失敗只剩「aos-agent ctl ls --json failed」看不出原因（使用者「兩個都記下來」）

## 併進來的（11-22 整理，照 progress 整理報告組 2）

- later-1115「11-15 意見裡「之後再說」的」原文（逐字）：stack 遷移、aos-frontend 大修（使用者 11-17：之後整個大修大重構；環境變數名、`API.md` 還沒跟著改名——11-18 查仍是 `VIEW_*`、`view-api/0`）、systemd 規則、全景頁為何常掛
  - 其中「stack 遷移」已被 11-22 的 `_stack` 規劃與線 1～6、9 蓋過；其餘（aos-frontend 大修、`VIEW_*` 改名、systemd 規則、全景頁為何常掛）歸這條。
- refactor-tidy-inventory 剩的「拆 aos-frontend（前端先不動，等大修）」。
- 整理報告：搬家後 `~/aos-home` 只剩 llm，`VIEW_TOOLS` 寫死 `~/aos-home/ws/tools` 會更不對；`aos-eca-frontend` 掛著沒事，名字與職責還沒答。
- 同一件、沒併的：waiting-1121 第 7 項（大修盤點 14 項，在 frontend-備妥-1121），那條屬等使用者回答，不動。
