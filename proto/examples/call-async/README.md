# call-async

跑這個會看到父地呼叫子地（脫節，子自己有鐘），父不等它做完，過幾格再去看結果落點 `out/child-said.txt` 有沒有東西。

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
python3 ../../aos.py exec .   # 第 0 格：ask 這步登記子地的鐘，立刻算成功，推到 wait
python3 ../../aos.py exec .   # 第 1 格：wait 還沒等到，HOLD
python3 ../../aos.py exec .   # 第 2 格：wait 等到了，推到 print
python3 ../../aos.py exec .   # 第 3 格：print，讀 out/child-said.txt 印出來
cat "$AOS_HOME/.aos/registry.json"   # 看子地登記在哪
```

如果家裡有 `aos daemon start` 在跑（`AOS_HOME` 要跟這裡一致），子地的鐘就交給 daemon 撐；沒有 daemon 的話，`exec` 發現登記表裡沒有活著的 `daemon_pid`，會自己 detach 一支 `aos run child --register` 去把子地跑到閒著（WRITER-BRIEF 4.11 第 6 條）。`run.sh` 就是走這條自動 detach 的路，不特別開 daemon。

## 這個範例在示範什麼

- `call` 步 `mode:"async"`，帶 `clock:{"kind":"until","until":"idle"}`：這步一登記完子地的時鐘就立刻成功，父不等子做完。
- 下一步 `await` 拿同一個 `result` 路徑，帶 `max_ticks`：每格看一次三態，沒等到就 HOLD，超過 `max_ticks` 就失敗（`await_timeout`）。
- 子地自己有鐘（脫節），跟 call-sync 那種「父每格幫子跑一次」不一樣。
- 登記表 `$AOS_HOME/.aos/registry.json` 記著子地登記了什麼時鐘、誰是父。
