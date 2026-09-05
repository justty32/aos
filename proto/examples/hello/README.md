# hello

跑這個會看到一串三步依序把一句話寫進暫存檔、讀出來、再印到螢幕上：`hello from aos`。

## 怎麼跑

```sh
proto/examples/hello/run.sh
```

或手動一步一步來（方便看每一格發生什麼）：

```sh
cd proto/examples/hello
python3 ../../aos.py init .
python3 ../../aos.py exec .   # 第 0 格：write，寫檔（有 expect，兩頻道判成敗之一）
python3 ../../aos.py exec .   # 第 1 格：read，複製檔案（沒 expect，靠結束碼判成敗）
python3 ../../aos.py exec .   # 第 2 格：print，印出來，串跑完
python3 ../../aos.py status . # 看游標與狀態
```

## 這個範例在示範什麼

- 一條串三步：`write`（跑一筆指令）→`read`→`print`，靠 `then` 接起來。
- `write` 那步宣告了 `expect`：產出的檔在＝成功，`<expect>.status.json` 在＝失敗——這是「兩頻道判成敗」的其中一頻道。`read`／`print` 沒宣告 `expect`，退回看結束碼（另一頻道）。
- `${frame}`、`${land}`、`${tick}` 三個暫存器都在用：`${frame}` 是這條串專屬的暫存資料夾，`${land}`、`${tick}` 秀進寫進去的內容裡。
