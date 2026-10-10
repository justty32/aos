## A. 指令與原始輸出

工作目錄是 `/home/lorkhan/repo/simple_tools/aos-wt/MN4`。README 中的 `/tmp/menu-try` 全部改用 `/tmp/mn4-play/luna/r1/menu-try`。repo 內沒有檔案被修改。

### 第一次跑

讀取指定文件：

```sh
cat /home/lorkhan/repo/simple_tools/aos-wt/MN4/proto7-2/packs/menu/README.md
```

README 原文說明了第一次跑的步驟和預期輸出。

依 README 建立工作資料夾、執行 `run` 和 `status`，再讀輸出檔：

```sh
mkdir -p /tmp/mn4-play/luna/r1/menu-try
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r1/menu-try proto7-2/packs/menu/examples/hello/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r1/menu-try
cat /tmp/mn4-play/luna/r1/menu-try/menu/hello/out/reply.txt
cat /tmp/mn4-play/luna/r1/menu-try/menu/hello/out/sent.txt
```

輸出：

```text
選單 hello：做完，寫了 out/reply.txt
選單 hello：做完，寫了 out/reply.txt
小明，開會通知已收到，謝謝！
給 小明：小明，開會通知已收到，謝謝！
```

### 故意弄壞

**a. 把不存在的資料夾當第一個參數：**

```sh
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r1/no-such-folder proto7-2/packs/menu/examples/hello/menu.json
```

輸出：

```text
aos7-menu: node 不在。給存在的資料夾，例如 ~/my-node
```

我看得懂：第一個參數指定的工作資料夾不存在；依訊息先建立資料夾再跑。

**b. 複製 hello，在複本刪除 `who` 的 `exit`：**

先複製範例並建立新的空工作資料夾：

```sh
mkdir -p /tmp/mn4-play/luna/r1/my /tmp/mn4-play/luna/r1/bad-work
cp -R proto7-2/packs/menu/examples/hello /tmp/mn4-play/luna/r1/my/hello-bad
```

第一次修改指令用錯 JSON 結構，沒有改動成功：

```sh
python3 -c 'import json; p="/tmp/mn4-play/luna/r1/my/hello-bad/menu.json"; d=json.load(open(p)); d["layers"][0]["options"].pop(); json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)'
```

輸出：

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; p="/tmp/mn4-play/luna/r1/my/hello-bad/menu.json"; d=json.load(open(p)); d["layers"][0]["options"].pop(); json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)
                                                                                         ~~~~~~~~~~~^^^
KeyError: 0
```

只讀了複本中的 JSON，確認 `layers` 是以名稱為鍵的物件後，改用正確指令刪除 `who.exit` 並執行：

```sh
python3 -c 'import json; p="/tmp/mn4-play/luna/r1/my/hello-bad/menu.json"; d=json.load(open(p)); del d["layers"]["who"]["exit"]; json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)'
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r1/bad-work /tmp/mn4-play/luna/r1/my/hello-bad/menu.json
```

輸出：

```text
aos7-menu: 層 who 缺出口 exit。每個問的層都要有，例 "exit": {"text": "都不是，要你決定"}。請改好選單再跑，例如參考 examples/hello/menu.json
```

我看得懂缺少哪個欄位，也知道可以參考訊息提供的格式補回 `exit`。

**c. 複製乾淨 hello，讓 `practice.json` 只剩第一句：**

```sh
mkdir -p /tmp/mn4-play/luna/r1/my-clean /tmp/mn4-play/luna/r1/short-work
cp -R proto7-2/packs/menu/examples/hello /tmp/mn4-play/luna/r1/my-clean/hello
python3 -c 'import json; p="/tmp/mn4-play/luna/r1/my-clean/hello/practice.json"; d=json.load(open(p)); d["replies"]=d["replies"][:1]; json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)'
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r1/short-work /tmp/mn4-play/luna/r1/my-clean/hello/menu.json
```

`run` 輸出：

```text
aos7-menu: 練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆
```

接著執行 `status`：

```sh
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r1/short-work
```

輸出：

```text
選單 hello：停下——練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆
```

我知道練習腳本回答不夠，訊息也說要補足 `practice.json`；但單看這句「換 `--run` 重走」時，不完全確定 `--run` 該放在哪個位置。

**d. 已完成的工作再跑一次，再照 README 從頭走：**

```sh
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r1/menu-try proto7-2/packs/menu/examples/hello/menu.json
rm -r /tmp/mn4-play/luna/r1/menu-try/menu/hello
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r1/menu-try proto7-2/packs/menu/examples/hello/menu.json
cat /tmp/mn4-play/luna/r1/menu-try/menu/hello/out/reply.txt
cat /tmp/mn4-play/luna/r1/menu-try/menu/hello/out/sent.txt
```

兩次 `run` 各自輸出：

```text
選單 hello：做完，寫了 out/reply.txt
選單 hello：做完，寫了 out/reply.txt
```

兩個 `cat` 各自輸出：

```text
小明，開會通知已收到，謝謝！
給 小明：小明，開會通知已收到，謝謝！
```

刪除 WORK：

```sh
rm -r /tmp/mn4-play/luna/r1/menu-try
```

輸出：無。

## B. 五題

1. **AI 每次看到什麼？要怎麼回答？**  
   每次只看到目前這一層的題目和選項。選擇題回一行 `選：` 加編號；需要寫字的層再回一行 `格：` 加內容。

2. **「練習用的 AI」是什麼？花不花錢？為什麼範例有一次被要求重回？**  
   它是不連網、不花錢的練習模式，照旁邊 `practice.json` 的句子依序回答。範例某次回答漏了 `格：`，格式不對，所以被要求依格式再回答一次。

3. **hello 選單的三層各做什麼？寫出的東西放在哪？**  
   第一層選要回小明或小華；第二層寫一句回覆並存成 `out/reply.txt`；第三層由登記的小工具把回覆「寄出」，結果寫成 `out/sent.txt`。工作資料夾下的路徑是 `menu/hello/out/`。

4. **每層最後一個編號是什麼？AI 選它會怎樣？**  
   最後一個編號永遠代表「都不行，要人決定」。AI 選它就停下來等人處理。README 沒列出 hello 每層選項實際編號的完整清單，所以我不能只根據這份文件寫出各層編號。

5. **從頭再走一次怎麼做？做完後再打同一個 `run` 會怎樣？**  
   刪掉工作資料夾裡的 `menu/hello` 再跑 `run`。對已完成的工作再次跑相同 `run`，只會再印「做完」，不會重走或再問 AI。

## C. 指令數與新概念

第一次跑依 README 共用了 **2 個指令**，不算 `mkdir`、`cat`：

1. `python3 ... aos7-menu run ...`
2. `python3 ... aos7-menu status ...`

第一次跑前要先懂 README 列出的 **4 個詞**：選單、一層、練習用的 AI、工作資料夾。

## D. 五項評分

| 標準 | 分數 | 例子 |
|---|---:|---|
| 容易上手 | 9/10 | 給了可照抄的第一次跑指令和預期輸出；只需先建立工作資料夾。 |
| 容易理解 | 8/10 | 四個詞和 hello 流程解釋清楚；但「最後一個編號」沒有列出各題實際有哪些編號。 |
| 複雜的藏起來 | 9/10 | 第一次用只需跑選單，不必設定模型或了解工具登記。 |
| 外層控制結構簡單但全面 | 8/10 | `run`、`status` 和刪除後重跑涵蓋基本流程；錯誤時也有原因和修正方向。 |
| 要背的少 | 9/10 | 入門只需理解四個詞，並照著 `run`、`status` 指令操作。 |

**總分：8.6/10。**

逐條扣分點：

- **容易上手：**「沒跑成時」那行的範例 `aos7-menu: node 不在`，`node` 是什麼要讀到後面的括號才知道；詞彙有點突然。
- **容易理解：**「最後一個編號永遠是……」沒有告訴我 hello 每一層選項的實際編號；「選：1」只舉了一個例子。
- **複雜的藏起來：**這項扣 1 分主要因為 `practice.json` 是一個需要知道位置與用途的額外檔案，不過 README 已解釋它。
- **外層控制結構簡單但全面：**出錯訊息說「換 `--run` 重走」，但本文件沒提供帶 `--run` 的完整命令，容易讓第一次使用者猜參數位置。
- **要背的少：**得記住 `run`、`status`、`out/reply.txt`、`out/sent.txt` 和刪除 `menu/hello` 的重跑方式；README 有示範，但指令仍不短。

## E. 一句話

用 ELI5 的方式說，這東西就是照順序問 AI 小問題、把答案存起來再做指定動作；第一次用不複雜。