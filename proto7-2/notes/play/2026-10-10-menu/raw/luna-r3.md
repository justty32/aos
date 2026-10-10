A. 實際操作與原始輸出

所有文件範例中的 `/tmp/menu-try` 都替換成 `/tmp/mn4-play/luna/r3/menu-try`。我從專案目錄 `/home/lorkhan/repo/simple_tools/aos-wt/MN4` 執行命令。

**1. 第一次跑**

```sh
mkdir -p /tmp/mn4-play/luna/r3/menu-try
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/menu-try proto7-2/packs/menu/examples/hello/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r3/menu-try
cat /tmp/mn4-play/luna/r3/menu-try/menu/hello/out/reply.txt
cat /tmp/mn4-play/luna/r3/menu-try/menu/hello/out/sent.txt
```

原始輸出：

```text
選單 hello：做完，寫了 out/reply.txt
選單 hello：做完，寫了 out/reply.txt
小明，開會通知已收到，謝謝！
給 小明：小明，開會通知已收到，謝謝！
```

**2a. 第一個參數給不存在的資料夾**

```sh
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/no-such-node proto7-2/packs/menu/examples/hello/menu.json
```

```text
aos7-menu: node 不在。給存在的資料夾，例如 ~/my-node
```

這行看得懂：工作資料夾不存在；建立資料夾後再試。

**2b. 複製 hello，刪除 who 層的 exit，再用空工作資料夾跑**

```sh
mkdir -p /tmp/mn4-play/luna/r3/my
cp -r proto7-2/packs/menu/examples/hello /tmp/mn4-play/luna/r3/my/hello-broken
mkdir -p /tmp/mn4-play/luna/r3/empty-b
python3 -c 'import json; p="/tmp/mn4-play/luna/r3/my/hello-broken/menu.json"; d=json.load(open(p)); del d["layers"]["who"]["exit"]; json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)'
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/empty-b /tmp/mn4-play/luna/r3/my/hello-broken/menu.json
```

```text
aos7-menu: 層 who 缺出口 exit。每個問的層都要有，例 "exit": {"text": "都不是，要你決定"}。請改好選單再跑，例如參考 examples/hello/menu.json
```

這行大致看得懂：`who` 層少了 `exit`，要補上。例子和修正方向都有給。

**2c. 複製乾淨 hello，把 practice.json 留第一句，跑 run 和 status**

```sh
cp -r proto7-2/packs/menu/examples/hello /tmp/mn4-play/luna/r3/my/hello-short
python3 -c 'import json; p="/tmp/mn4-play/luna/r3/my/hello-short/practice.json"; d=json.load(open(p)); d["replies"]=d["replies"][:1]; json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)'
mkdir -p /tmp/mn4-play/luna/r3/empty-c
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/empty-c /tmp/mn4-play/luna/r3/my/hello-short/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r3/empty-c
```

`run` 原始輸出：

```text
aos7-menu: 練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆
```

因為 `run` 已停止，我再單獨執行 status：

```sh
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r3/empty-c
```

```text
選單 hello：停下——練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆
```

**2d. 已完成的 WORK 再跑同一個 run，然後照 README 從頭重走**

```sh
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/menu-try proto7-2/packs/menu/examples/hello/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/menu-try proto7-2/packs/menu/examples/hello/menu.json
```

兩次原始輸出都一樣：

```text
選單 hello：做完，寫了 out/reply.txt
```

接著照 README 刪除這次紀錄，再跑同一個 run：

```sh
rm -r /tmp/mn4-play/luna/r3/menu-try/menu/hello
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r3/menu-try proto7-2/packs/menu/examples/hello/menu.json
```

```text
選單 hello：做完，寫了 out/reply.txt
```

最後照 README 刪掉 WORK：

```sh
rm -r /tmp/mn4-play/luna/r3/menu-try
```

沒有輸出。其他複本與測試資料都在 `/tmp/mn4-play/luna/r3/` 底下，沒有改 repo 裡的檔案。

**操作中的一次失誤及修正**

我第一次嘗試刪掉 `who` 層的出口時，把 `layers` 當成陣列，指令失敗：

```sh
python3 -c 'import json; p="/tmp/mn4-play/luna/r3/my/hello-broken/menu.json"; d=json.load(open(p)); d["layers"][0]["options"].pop(); json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)'
```

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; p="/tmp/mn4-play/luna/r3/my/hello-broken/menu.json"; d=json.load(open(p)); d["layers"][0]["options"].pop(); json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)
                                                                                            ~~~~~~~~~~~^^^
KeyError: 0
```

我在複本中查看 JSON 後確認 `layers` 是以層名稱為鍵的物件，改用 `d["layers"]["who"]` 刪除 `exit`。查看複本的指令是：

```sh
python3 -c 'import json; p="/tmp/mn4-play/luna/r3/my/hello-broken/menu.json"; d=json.load(open(p)); print(json.dumps(d,ensure_ascii=False,indent=2))'
```

B. 五題

1. **AI 每次看到什麼？要怎麼回答？**  
   每次只看到目前那一層的題目和編號選項。一般選擇題回一行 `選：N`；要寫字的層，還要再回一行 `格：`，後面接內容。

2. **「練習用的 AI」是什麼？花不花錢？為什麼範例有一次被要求重回？**  
   它不是真模型，而是照同資料夾 `practice.json` 的回覆一行一句念；不連網、不花錢。範例第二句故意漏了 `格：`，格式不合，所以被要求重回一次。

3. **hello 選單三層各做什麼？寫出的東西放在哪？**  
   第一層選要回小明還是小華；第二層寫一句回覆，存為 `out/reply.txt`；第三層由小工具執行寄出，結果存為 `out/sent.txt`。紀錄與輸出都在工作資料夾的 `menu/hello/` 底下。

4. **每層最後一個編號是什麼？AI 選了它會怎樣？**  
   第一層與第二層最後一個編號都是出口，表示 AI 做不了、需要人決定。AI 選出口後，選單停下來等人處理；README 範例的出口文字是請人補充必要資訊。第三層是工具執行，沒有 AI 編號選項。

5. **想從頭再走一次怎麼做？已完成後再打同一個 run 會怎樣？**  
   可以刪掉 `menu/hello/` 紀錄再跑，或在 `run` 最後加 `--run 新名字` 另開一份。已完成後再打同一個 run，只會再印「做完」，不會重走或再問 AI。

C. 第一次跑用了幾個指令？需要先懂幾個新概念？

第一次跑步驟是 `mkdir -p`、`run`、`status`、兩次 `cat`。不算 `mkdir`、`cat`，也不把依 README 先進入專案目錄的 `cd` 算入，**共 2 個指令：run 和 status**。

README 的入門段先介紹了 **4 個詞**：選單、一層、練習用的 AI、工作資料夾（node）。

D. 五條標準評分

| 標準 | 分數 | 例子與扣分點 |
|---|---:|---|
| 容易上手 | 9/10 | README 有可照抄的完整命令、預期輸出與檔案位置。扣 1 分：`run` 後面要接工作資料夾和選單檔，初學者得先分清兩個參數。 |
| 容易理解 | 9/10 | 用寄信範例把選擇、寫回覆、執行工具串起來。扣 1 分：`node` 是工作資料夾的別名，第一次看到 `node 不在` 可能不直覺。 |
| 複雜的藏起來 | 9/10 | 入門明確說其他欄位、真 AI 與更多選項第一次用不到。扣 1 分：輸出路徑中的 `menu/hello/out/` 對第一次用的人有點長。 |
| 外層控制結構簡單但全面 | 8/10 | `run`、`status`、停下後重走、完成後重跑都有說明。扣 2 分：`--run`、`exit`、`practice.json` 這些詞需要依上下文理解；停下原因雖列了三種，實際怎麼處理仍要讀完整段落。 |
| 要背的少 | 9/10 | 日常入門只要記得先建工作資料夾，再跑 `run` 和 `status`。扣 1 分：重走要記住刪紀錄或加 `--run` 兩種方法，還要分辨各自用途。 |

**總分：8.8/10**（五項平均）。

扣分點來自 README 的「第一次跑」與「沒跑成、停下、重走」段落：`node`、`--run`、`exit` 是較可能讓新手停下來猜意思的字；`menu/hello/out/` 是較長的路徑。

E. 一句話

ELI5 之後，它對新手不算複雜：照著建立資料夾、跑命令，就能讓 AI 一次回答一題並把結果交給預先準備好的小工具。