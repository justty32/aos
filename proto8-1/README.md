# proto8-1 — tasks：在 aos_inst 之上的小程式

← [proto8](../proto8/README.md)｜用到的 lib：[proto8/lib](../proto8/lib/README.md)

2026-10-12 開。使用者說：tasks 像 lisp 的基礎函數；**每支跟 aos_inst 一樣是獨立程式**，daemon 跑 inst.json，argv[0] 就是它（tasks 只是這類程式的統稱，會有 aos-seq 之類）。指示詞照舊只負責把大 JSON 拆成小檔，跟 tasks 無關。

```
loop ──跑──> top/inst.json      argv: ["aos-seq", "a", "inner"]
                 └─ aos-seq ──起 aos_inst.py──> a，再 inner
                                                 inner/inst.json   argv: ["aos-par", "x", "y"]
```

巢狀不用新語法：某個 inst.json 的 argv 再寫一支 tasks 程式就好（`(seq a (par x y))`）。

原語只做最精簡的四個：seq、par、if、not（使用者 10-12 定；or 可以用 if＋not 拼）。要數字參數的（retry、timeout）和 while 不做。

另外放了 **aos-tick**：tick-tock 就是一個時鐘（[CONCEPTS C-44](../proto8/CONCEPTS.md)），不包任務、不保證什麼；每跑一次把 FILE 裡的回合數加一。節奏、停、只走 N 回合交給 loop（loop.json 的 `inst` 寫 aos-tick，外層給 times／interval_ms，停＝它的 ctl.json 寫 `"paused": true`），有沒有 daemon 都行；打包是規範，之後由 kernel 做。

## 程式

| 位置 | 是什麼 |
|---|---|
| `lib/aos_seq.py` | 照順序跑，像 `&&`：第一個非 0 就停，退出碼＝它的碼（各自讀 aos_inst 結果的 `code`） |
| `lib/aos_par.py` | 一起跑、等全部結束：全 0 回 0，否則照參數順序第一個非 0 的碼 |
| `lib/aos_if.py` | `aos-if COND THEN [ELSE]`：條件回 0 跑 THEN、否則跑 ELSE；退出碼取跑到的那支，沒 ELSE 又不成立＝0 |
| `lib/aos_not.py` | `aos-not TARGET`：0 變 1、非 0 變 0（自己出錯和被訊號停掉不反過來） |
| `lib/aos_tick.py` | `aos-tick FILE`：讀出回合數 n、寫回 n＋1（不在＝0，先寫 `.名字.tmp` 再改名）；stdout 不吐東西；內容不對／讀寫不了／用法不對在 stderr 吐一份 `{"error": {"code", "msg"}}`（同 aos_cli）、退出碼 1、FILE 不動 |
| `lib/aos_tasks.py` | 共用：找 proto8/lib、一次讀好全部 inst、起 `aos_inst.py`、讀它 stdout 結果的 `code`、接訊號轉給它們 |
| `bin/aos-seq`、`bin/aos-par`、`bin/aos-if`、`bin/aos-not`、`bin/aos-tick` | 薄入口（sh，`exec python3 ../lib/aos_*.py`）；放進 PATH 就能在 argv 寫 `"aos-seq"` |
| `tests/test_tasks.py`、`tests/test_tick.py` | unittest |
| `demo/` | 用 daemon 跑一棵 tasks 樹（檢查→重試→並行→收尾），`python3 proto8-1/demo/run.py`；寫起來的發現見 [demo/README.md](demo/README.md) |

tasks 的共同規矩（aos-tick 不跑 inst，不適用；細節在各檔檔頭）：

- 參數是 inst 的 TARGET（同 aos_inst：`.json` 或資料夾），相對路徑從自己的 cwd 算。
- **先全部讀好、驗過才開始**；有一個不對就在 stderr 吐一份錯誤、退出碼 1，一個都不跑。個數不對也是 1（`Usage`）。tasks 自己的錯一律 1（10-15 晚使用者「按照推薦」，原 125／127／126／128＋N）；seq／par／if 回子程式的碼是透明轉交，aos-not 是述詞（N-34）。inst **不必寫 `exit`**（選填，exit 檔只當過渡）。
- 每個 inst 用子程序 `aos_inst.py TARGET` 跑；**接它的 stdout，子程式的結束碼＝那份結果 JSON（N-12、[N-30](../proto8/NORMS/03-基礎設施-inst.md)）的 `code`**（aos_inst 的退出碼只說它自己，不傳子程式的碼）。寫了 `stdout_inherit` 時子程式的輸出會混在前面，從最後一行往回找第一份帶 `code` 的；找不到＝吐 `ResultUnreadable`、算 1。結果只給 tasks 讀，不漏進 tasks 的 stdout。
- **三扇門（N-12）**：tasks 自己的 stdout 不吐東西（空的 JSON 串流，結果就是退出碼；[N-34](../proto8/NORMS/07-基礎設施-組合子.md)）；自己的錯誤直接用 proto8 `aos_cli` 的 `error()`，在 stderr 吐 `{"error": {"code", "msg"}}`，一份一行，跟 aos_inst 的錯誤同一個格式。
- 跑的途中 aos_inst 自己出錯：它自己在 stderr 吐一份 `{"error": {"code", "msg"}}`（N-12），那一個算 1（seq 就停在那裡、if 的條件起不來不跑 ELSE）。
- 收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的 aos_inst（它再轉給子程式、過 inst 的 `grace_ms` 再 SIGKILL）、不再起新的，stderr 一份 `Signaled`（帶訊號號碼）、退出碼 1。
- **子程式不開新 session**，留在自己的群組裡：loop 整群收的時候一起收到，不會變孤兒。
- 結束碼數字只有 0／非 0 是確定的，其他供參考。

## 測試

```
python3 -m unittest discover -s proto8-1/tests
```

只用標準庫，21 個（tasks 14、tick 7）、約 3 秒；用 proto8 的 `aos_loop.py` 的兩個：起 aos-seq、ctl.json 寫 stop now 後確認孫程式被收掉；跑 aos-tick 三次、FILE＝3。
