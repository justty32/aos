以下只依指定的 `README.md` 和實際執行結果整理。所有工作資料都放在 `/tmp/mn4-play/luna/r2/`；最後已照 README 刪除 `WORK`。

## A. 操作指令與原始輸出

**1. 第一次跑**

先建立工作資料夾，再跑 `run`、`status`，並查看兩個輸出檔：

```sh
mkdir -p /tmp/mn4-play/luna/r2/menu-try
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r2/menu-try proto7-2/packs/menu/examples/hello/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r2/menu-try
cat /tmp/mn4-play/luna/r2/menu-try/menu/hello/out/reply.txt
cat /tmp/mn4-play/luna/r2/menu-try/menu/hello/out/sent.txt
```

原始輸出：

```text
選單 hello：做完，寫了 out/reply.txt
選單 hello：做完，寫了 out/reply.txt
小明，開會通知已收到，謝謝！
給 小明：小明，開會通知已收到，謝謝！
```

**2a. 用不存在的資料夾當第一個參數**

```sh
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r2/no-such-folder proto7-2/packs/menu/examples/hello/menu.json
```

```text
aos7-menu: node 不在。給存在的資料夾，例如 ~/my-node
```

看得懂；知道要先建立資料夾。

**2b. 刪掉複本 `menu.json` 裡 `who` 的 `exit`，用新工作資料夾跑**

```sh
cp -R proto7-2/packs/menu/examples/hello /tmp/mn4-play/luna/r2/my/hello-broken
python3 - <<'PY'
import json
p='/tmp/mn4-play/luna/r2/my/hello-broken/menu.json'
with open(p, encoding='utf-8') as f: d=json.load(f)
d['layers']['who'].pop('exit')
with open(p,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2)
PY
mkdir -p /tmp/mn4-play/luna/r2/broken-run
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r2/broken-run /tmp/mn4-play/luna/r2/my/hello-broken/menu.json
```

```text
aos7-menu: 層 who 缺出口 exit。每個問的層都要有，例 "exit": {"text": "都不是，要你決定"}。請改好選單再跑，例如參考 examples/hello/menu.json
```

看得懂；知道要在 `who` 層補回 `exit`。

**2c. 複製乾淨 hello，把 `practice.json` 改成只剩第一句，再跑 `run` 和 `status`**

```sh
cp -R proto7-2/packs/menu/examples/hello /tmp/mn4-play/luna/r2/my/hello-short
python3 - <<'PY'
import json
p='/tmp/mn4-play/luna/r2/my/hello-short/practice.json'
with open(p, encoding='utf-8') as f: d=json.load(f)
d['replies']=d['replies'][:1]
with open(p,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2)
PY
mkdir -p /tmp/mn4-play/luna/r2/short-run
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r2/short-run /tmp/mn4-play/luna/r2/my/hello-short/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r2/short-run
```

`run` 印出：

```text
aos7-menu: 練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆
```

`run` 停下後沒有接著執行同一串命令中的 `status`，所以另外打：

```sh
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/mn4-play/luna/r2/short-run
```

```text
選單 hello：停下——練習腳本用完了。換 --run 重走，並補足 practice.json 的回覆
```

看得懂；知道要補足練習回覆，並可用新的 `--run` 名字重走。

**2d. 在已完成的 WORK 上再跑同一個 `run`，再照 README 從頭走一次**

```sh
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r2/menu-try proto7-2/packs/menu/examples/hello/menu.json
rm -r /tmp/mn4-play/luna/r2/menu-try/menu/hello
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/mn4-play/luna/r2/menu-try proto7-2/packs/menu/examples/hello/menu.json
rm -r /tmp/mn4-play/luna/r2/menu-try
```

兩次 `run` 各印出：

```text
選單 hello：做完，寫了 out/reply.txt
選單 hello：做完，寫了 out/reply.txt
```

第一次只是回報已完成，沒有重走；刪除 `menu/hello` 的紀錄後再跑，才從頭走一次。最後已執行 README 指定的刪除 WORK 命令。

## B. 五題

1. **AI 每次看到什麼？它要怎麼回答？**  
   每次只看到目前那一層的問題和編號選項，回答一行 `選：N`。需要寫字的層，還要再回一行 `格：`，後面接寫的內容。

2. **「練習用的 AI」是什麼？花不花錢？為什麼範例裡有一次被要求重回？**  
   它是在沒有真模型時，照 `practice.json` 一句句給預先寫好的回答；不連網、不花錢。範例第二句故意漏掉 `格：`，格式不合要求，所以被要求重回一次。

3. **hello 選單的三層各做了什麼？寫出來的東西放在哪？**  
   第一層選收件人；第二層寫一句回覆；第三層由小工具執行寄送，範例是把寄送結果寫成檔案。走過的紀錄和輸出都在工作資料夾的 `menu/hello/` 底下；回覆在 `out/reply.txt`，寄送結果在 `out/sent.txt`。

4. **每層最後一個編號是什麼？AI 選了它會怎樣？**  
   每個問答層的最後一個編號代表「都不行，要人決定」。AI 選它就會停下來等人處理。

5. **想從頭再走一次要怎麼做？對已經做完的再打一次同一個 run 會怎樣？**  
   可以刪掉 `menu/hello/` 的紀錄後再跑同一個 `run`，或在命令最後加 `--run 新名字`，另走一份紀錄。已完成的流程再跑同一個 `run` 只會印出「做完」，不會重走。

## C. 指令數與新概念

第一次跑所用命令共 **4 個**：建立資料夾、`run`、`status`、查看 `reply.txt`、查看 `sent.txt`。依 README 的算法，不算 `mkdir`、`cat`，所以是 **2 個指令**（`run` 和 `status`）。

README 說第一次先懂 **4 個詞**：

1. 選單
2. 一層
3. 練習用的 AI
4. 工作資料夾

## D. 五條標準評分

1. **容易上手：9/10**  
   給了可直接複製的第一次跑命令和預期輸出。扣 1 分：開頭連結 `← [packs](../../INDEX.md)` 對首次使用者用途不明，會想知道是否需要先去看。

2. **容易理解：8/10**  
   四個詞和三步流程有例子。扣 2 分：在「一層」的說明中，「要它寫字的層」沒有直接稱為第二層，讀者要從後面的流程推回去理解。

3. **複雜的藏起來：9/10**  
   明確說第一次不需要懂 JSON 欄位、登記工具或接真 AI。扣 1 分：文末一次列出 `ADVANCED.md`、`spec.md` 和 `--help`，對新手仍可能顯得要看很多東西。

4. **外層控制結構簡單但全面：8/10**  
   從建立工作資料夾、跑選單、查看狀態，到停下、重走和清除都有說明。扣 2 分：錯誤例子裡的 `node` 和 `--run` 都是新詞，雖然有解釋，但新手需要在同一段吸收多個概念。

5. **要背的少：9/10**  
   第一次只需記得 `run` 和 `status`，其他處理方式可以照文件做。扣 1 分：`menu/hello/out/`、`reply.txt`、`sent.txt`、`--run` 等名稱在故障和重走時都要辨認。

**總分：8.6/10**（五項平均）

## E. ELI5 一句話

**把大問題切成一題一題的選擇題，AI 依格式回答，程式照答案做事；照著範例用並不複雜。**