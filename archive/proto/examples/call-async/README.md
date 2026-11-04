# call-async

跑這個會看到父地呼叫子地（脫節，子自己有鐘），父不等它做完，過幾格再去看結果落點 `out/child-said.txt` 有沒有東西。

**要先有 daemon。** 裁決 P-01（2026-09-05）：沒有 daemon 在跑時，脫節呼叫**當場失敗**，
父指定的結果落點旁邊會多一個 `out/child-said.txt.status.json`，裡面寫
`{"state":"failed","reason":"no_daemon",…}`；那條串照 `on_fail` 走，沒寫 `on_fail` 就停在原地。

## 怎麼跑

```sh
proto/examples/call-async/run.sh
```

`AOS_HOME` 一定要指到範例自己的暫存目錄（`run.sh` 用的是 `./.home`），不要用使用者真正的 `~`：

```sh
cd proto/examples/call-async
export AOS_HOME="$(pwd)/.home"
python3 ../../aos.py init .
python3 ../../aos.py init child
python3 ../../aos.py daemon start --every 200   # ← 先起 daemon，不然下一步就 no_daemon
python3 ../../aos.py exec .   # 第 0 格：ask 這步登記子地的鐘，立刻算成功，推到 wait
python3 ../../aos.py exec .   # 第 1 格：wait 還沒等到，HOLD（daemon 這時在起 aos run child）
python3 ../../aos.py exec .   # 第 2 格：wait 等到了，推到 print
python3 ../../aos.py exec .   # 第 3 格：print，讀 out/child-said.txt 印出來
cat "$AOS_HOME/.aos/registry.json"   # 看子地登記在哪
python3 ../../aos.py daemon stop
```

## 這個範例在示範什麼

- `call` 步 `mode:"async"`，帶 `clock:{"kind":"until","until":"idle"}`：這步把子地的時鐘登進登記表就立刻成功，父不等子做完。真正去起 `aos run child --register` 的是 daemon（裁決 G-01：daemon 只當看管者）。
- 下一步 `await` 拿同一個 `result` 路徑，帶 `max_ticks`：每格看一次三態，沒等到就 HOLD，超過 `max_ticks` 就失敗（`await_timeout`）。
- 子地自己有鐘（脫節），跟 call-sync 那種「父每格幫子跑一次」不一樣。
- 子地的指令怎麼知道結果要寫哪？`AOS_RESULT`／`AOS_CALLER`／`AOS_ARG_*` 由 `aos run` 從登記表那筆（`result`／`parent`／`args`）重建出來——因為起它的是 daemon，拿不到父當初 exec 的環境。
- 登記表 `$AOS_HOME/.aos/registry.json` 記著子地登記了什麼時鐘、誰是父、結果落點在哪。

## 想看 `no_daemon` 長什麼樣

把上面那行 `daemon start` 拿掉再跑一次 `exec`，就會看到串失敗、`out/child-said.txt.status.json` 出現。
