# proto8-1 — tasks：在 aos_inst 之上的小程式

← [proto8](../proto8/README.md)｜用到的 lib：[proto8/lib](../proto8/lib/README.md)

2026-10-12 開。使用者說：tasks 像 lisp 的基礎函數；**每支跟 aos_inst 一樣是獨立程式**，daemon 跑 inst.json，argv[0] 就是它（tasks 只是這類程式的統稱，會有 aos-seq 之類）。指示詞照舊只負責把大 JSON 拆成小檔，跟 tasks 無關。

```
daemon ──跑──> top/inst.json    argv: ["aos-seq", "a", "inner"]
                 └─ aos-seq ──用 aos_inst.run()──> a，再 inner
                                                 inner/inst.json   argv: ["aos-par", "x", "y"]
```

巢狀不用新語法：某個 inst.json 的 argv 再寫一支 tasks 程式就好（`(seq a (par x y))`）。

原語只做最精簡的四個：seq、par、if、not（使用者 10-12 定；or 可以用 if＋not 拼）。要數字參數的（retry、timeout）和 while 不做。

另外放了 **aos-tick**：tick-tock 就是一個時鐘（[CONCEPTS C-44](../proto8/CONCEPTS.md)），不包任務、不保證什麼；每跑一次把 FILE 裡的回合數加一。節奏、停、只走 N 回合交給 daemon（argv 寫 aos-tick 的 inst，how 給 times／interval_ms，停＝pause）；打包是規範，之後由 kernel 做。

## 程式

| 位置 | 是什麼 |
|---|---|
| `lib/aos_seq.py` | 照順序跑，像 `&&`：第一個非 0 就停，退出碼＝它的碼 |
| `lib/aos_par.py` | 一起跑、等全部結束：全 0 回 0，否則照參數順序第一個非 0 的碼 |
| `lib/aos_if.py` | `aos-if COND THEN [ELSE]`：條件回 0 跑 THEN、否則跑 ELSE；退出碼取跑到的那支，沒 ELSE 又不成立＝0 |
| `lib/aos_not.py` | `aos-not TARGET`：0 變 1、非 0 變 0（自己出錯和被訊號停掉不反過來） |
| `lib/aos_tick.py` | `aos-tick FILE`：讀出回合數 n、寫回 n＋1（不在＝0，先寫 `.名字.tmp` 再改名）；內容不對／讀寫不了／用法不對印「代號: 白話」、退出碼 1、FILE 不動 |
| `lib/aos_tasks.py` | 共用：找 proto8/lib、一次讀好全部 inst、接訊號 |
| `bin/aos-seq`、`bin/aos-par`、`bin/aos-if`、`bin/aos-not`、`bin/aos-tick` | 薄入口（sh，`exec python3 ../lib/aos_*.py`）；放進 PATH 就能在 argv 寫 `"aos-seq"` |
| `tests/test_tasks.py`、`tests/test_tick.py` | unittest |
| `demo/` | 用 daemon 跑一棵 tasks 樹（檢查→重試→並行→收尾），`python3 proto8-1/demo/run.py`；寫起來的發現見 [demo/README.md](demo/README.md) |

tasks 的共同規矩（aos-tick 不跑 inst，不適用；細節在各檔檔頭）：

- 參數是 inst 的 TARGET（同 aos_inst：`.json` 或資料夾），相對路徑從自己的 cwd 算。
- **先全部讀好、驗過才開始**；有一個不對就印「代號: 白話」、退出碼 125，一個都不跑。個數不對也是 125。
- 跑的途中 aos_inst 自己出錯：印「代號: 白話」、那一個算 127＝找不到程式／126＝不能執行／125＝其他（同 aos_inst 命令列；seq 就停在那裡、if 的條件起不來不跑 ELSE）。
- 收到 SIGINT／SIGTERM／SIGHUP：收掉正在跑的（SIGTERM，過 2 秒 SIGKILL）、不再起新的，退出碼＝128＋訊號號碼。
- **子程式不開 new_session**，留在自己的群組裡：daemon 整群收的時候一起收到，不會變孤兒。
- 子程式的結束碼靠 `aos_inst.run()` 回傳（為此 proto8/lib 的 run() 改成回結束碼）。

## 測試

```
python3 -m unittest discover -s proto8-1/tests
```

只用標準庫，18 個（tasks 11、tick 7）、約 2 秒；用 proto8 的 `aos_loop` 的兩個：起 aos-seq、remove 後確認孫程式被收掉；跑 aos-tick 三次、FILE＝3。
