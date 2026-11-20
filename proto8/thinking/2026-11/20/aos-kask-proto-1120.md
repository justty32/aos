# 線 aos-kask-proto-1120 紀錄：「寄信問 kernel」放 body 的原型——只交 thinking，原型在暫存夾的乾淨複本

← [2026-11-20](README.md)｜成品：[aos-kask-proto-1120/](aos-kask-proto-1120/README.md)

頂層派。依據：使用者 11-20 看了 aos-kask-1120 的結果後說「我預期的是做一份特殊的syscall協議基底，專門用於詢問這個kernel吃啥資源宣告，然後有特殊信箱，處理這個信箱的程序是掛在特定hook上(或許有更好的方式？比如換成放在body？)。」，頂層問要不要派原型，他說「派，幫我放body吧」。只做放 body 這一種。

## 做了什麼

- 讀程式（HEAD `640f227dc` 的乾淨複本）：骨架 `round.py`／`letters.py`、兩種 kernel 的入口與範本（`kernel_llm/_entry`、`kernel/_entry`、start-api 的 `llm/`、`perm/`）、aos-daemon 的信箱（`daemon.cpp`、`mailbox.cpp`、`reconcile.cpp`）、aos-post 說明、`state_path.py`、`aos-llm` 的信箱位址。
- 原型：乾淨複本 `mine/` 的 `py/tools/aos/kernel/round.py` 加兩行、新檔 `kask.py`；`install.py` 裝在複本裡。
- 暫存樹：start-api 原樣抄出，根＋`llm`＋`perm` 掛同一塊板子，假腦。實跑三輪（`run.sh`、`run2.sh`、`run3.sh`），再照 06 的指令跑一次（`try.sh`）。
- 寫 `aos-kask-proto-1120/` 八份：README、00～06、02 附件。

## 證據

- 測試：`kernel/tests`、`kernel_llm/tests`、`kernel_gate/tests` 改前 122／80／20 支 OK，改後一樣 122／80／20 支 OK（`tests-before/`、`tests-after/`）。沒為原型寫新測試。
- 實跑輸出：`~/.aos/scratch/aos-kask-proto-1120/run.out`、`run2.out`、`run3.out`（03、04 節錄）。

## 對不上處

- 任務書說「今天掛 proc 的站會回假成功」：實跑確認（`{"applied": true}`），原型沒動這條路，所以還是這樣。
- 本來想示範「hook 壞了問句照答」：實際上每輪先答問句再死，但權限站是 loop，`exec` 退 1 時 aos-loop 也退出、等 daemon 重起，實跑問句等了 7.4 秒才回。寫進 03 第八節。
- llm kernel（daemon 的 body）壞掉時會怎樣沒試。
- 跟上一條線的數字：上一條線跑時機器忙（普通請求單獨 2.7 秒，今天 1.2 秒），03 註明只比形狀。

## 替使用者做的選擇

- 「放body」＝兩種 kernel 共用的骨架 `round.py`。
- 信箱 `<stack>/kask/`（跟 `requests/` 並排）：最不用動 daemon 的一種，寫明是權宜。
- 答問句在拿鎖之後、收信之前；一輪全答；不排隊、不過 hook、不記帳；每封重讀定義夾的 `kask.json`；沒放＝回 `null`＋原因；只認 `{"kernel_ask": true}`，別的鍵不看；寄錯信箱不管；兩種 kernel 回同一種形狀。每一條都列成 05 的題，沒當定案。
- 名字（`kask`、`kask.json`、`kernel_ask`、`AskBad`）全是示意；沿用上一條線的示意名與兩份示意宣告。

## 跟別線

- 只讀不碰：aos-pylib-k4-1120、aos-hook-drift-1120、aos-compact-twice-1120 的檔都沒碰；原型 diff 是在乾淨複本上，沒配合 hook 線之後要換的把手。
- 只交本線的 thinking 檔與日索引一列（`day_upsert`）。

## 收尾

- 行程：暫存樹用 `aos-daemon-ctl -d …/t/.stack shutdown` 收掉，`pgrep` 沒有本線的行程。開工時看到的 aos 行程（`/tmp/gdb-live-*` 那棵、一支 `aos-loop loop.json`、兩支 defunct）都是別線的，沒碰。
- 暫存：`~/.aos/scratch/aos-kask-proto-1120/`（`base/`、`mine/` 兩份乾淨複本，`mine/` 已裝；`t/` 暫存樹；`boxes/` 回信；腳本與輸出），沒刪。
