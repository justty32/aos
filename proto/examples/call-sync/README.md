# call-sync

跑這個會看到父地呼叫子地（同步，借父的鐘），子地把一句話寫到父指定的結果落點 `out/child-said.txt`，父地再讀出來印到螢幕上。

## 怎麼跑

```sh
proto/examples/call-sync/run.sh
```

或手動一步一步來：

```sh
cd proto/examples/call-sync
python3 ../../aos.py init .
python3 ../../aos.py init child
python3 ../../aos.py exec .   # 第 0 格：ask 這步呼叫子地，子地跑 warmup，還沒閒著，父停在原地
python3 ../../aos.py exec .   # 第 1 格：ask 再對子做一次 exec，子跑完 say、閒著了，父判三態＝成功
python3 ../../aos.py exec .   # 第 2 格：print，讀 out/child-said.txt 印出來
cat out/child-said.txt
```

## 這個範例在示範什麼

- `call` 步 `mode:"sync"`：父每格對子做一次 `aos exec`；子沒閒著（`warmup`→`say` 兩步），父的 `ask` 這步就停在原地不算失敗，要等好幾格。
- `result` 是**父指定的結果落點**（`out/child-said.txt`），不是固定路徑——子地完全不知道這個路徑寫在自己的原稿裡，是透過環境變數 `AOS_RESULT` 拿到的。
- 子地跑完閒著後，父看三態：結果檔在＝成功、`<結果落點>.status.json` 在＝失敗、都不在＝子地閒著但沒寫東西也算失敗。
- 父開子地時寫一筆呼叫記錄到 `.aos/calls/<call id>.json`，跑完可以去看。
