← [packs](../../INDEX.md)

**這是什麼**：讓 AI 一次只回答一個小問題——你先寫好一串選擇題，AI 每次只看一題、回一個編號（要它寫字的題目再多回一段字），真正動手的事由你準備好的程式做。
**一行跑起來**：`python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/menu-try proto7-2/packs/menu/examples/hello/menu.json`（先 `mkdir -p /tmp/menu-try`）
**看到什麼**：`選單 hello：做完，寫了 out/reply.txt`

## 先懂這四個詞

1. **選單**：一個 JSON 檔，裡面是一題一題的選擇題。範例 `examples/hello/menu.json` 是「回一封信」：先選回誰、再寫一句回覆、最後寄出。
2. **一層**：選單裡的一題。AI 每次只看到這一題和它的編號選項，回「選：1」這樣的一行；要它寫字的那層，第二行寫「格：」，後面接它寫的內容。每層最後一個編號叫**出口**，意思一律是「我做不了，要人決定」，字由寫選單的人自己定（範例第一層寫的是「缺少判斷先回誰的必要資訊，請人補充」）。AI 選出口，選單就停下來等你。範例選了小明後，第二層 AI 實際看到的完整提示：

   ~~~~text
   小明 的要求是「請確認收到開會通知。」請寫一句可直接交出的回覆，確認已收到對方提到的內容；資訊足夠就交出回覆。
   1. 交出這一格
   2. 缺少回覆所需的必要資訊，請人補充
   回法：第一行 選：N
   第二行起：先寫「格：」，後面（同一行或下一行起）到結尾放全文，原樣、不加 ``` 圍欄，全文後面不要再寫任何字
   這格的限制（只是說明，不要抄進格子）：最多 200 bytes、最多 1 行
   ~~~~

3. **練習用的 AI**：不給真模型時，回答照 `practice.json`（跟 `menu.json` 放在同一個資料夾）一句一句念，不連網、不花錢。範例裡第 2 句故意回錯格式，你會看到它被要求重回一次。
4. **工作資料夾**：你給的第一個參數（這裡是 `/tmp/menu-try`），要先存在；程式的訊息裡把它叫 **node**，是同一個東西。走過的紀錄放在它底下的 `menu/hello/`，寫出來的東西在 `menu/hello/out/`。

## 第一次跑

先 `cd` 進 aos 專案資料夾（就是你 git clone 下來的那個，裡面看得到 `proto7-2/` 資料夾），再打。`run` 後面接兩樣：工作資料夾、選單檔。

```sh
mkdir -p /tmp/menu-try
python3 proto7-2/packs/menu/bin/aos7-menu run /tmp/menu-try proto7-2/packs/menu/examples/hello/menu.json
python3 proto7-2/packs/menu/bin/aos7-menu status /tmp/menu-try
```

實跑輸出（2026-10-10，兩個指令各印一行、不到一秒）：

```text
選單 hello：做完，寫了 out/reply.txt
選單 hello：做完，寫了 out/reply.txt
```

第一行是 `run` 印的，第二行是 `status` 印的。看寫出來的東西：

```sh
cat /tmp/menu-try/menu/hello/out/reply.txt    # 小明，開會通知已收到，謝謝！
cat /tmp/menu-try/menu/hello/out/sent.txt     # 給 小明：小明，開會通知已收到，謝謝！
```

剛剛發生的事：

1. 第一層問「先回誰」（題目裡附了兩封信，小明那封是急件），練習用的 AI 回「選：1」＝小明。
2. 第二層要 AI 寫一句回覆。它第一次漏了「格：」，被要求照格式重回；第二次寫對了，這句被存成 `out/reply.txt`。
3. 第三層不問 AI：由登記好的小工具把回覆「寄出」，寫成 `out/sent.txt`。到這裡選單走完。

## 沒跑成、停下、重走

- 沒跑成時只印一行，說哪裡不對、怎麼辦。例：`aos7-menu: node 不在。給存在的資料夾，例如 ~/my-node`——工作資料夾還沒建，先 `mkdir -p` 再跑。選單或練習檔 JSON 壞掉時，訊息會指出第幾行第幾字，修好再跑。
- 停下時（AI 選了出口、連回錯 3 次、練習的句子用完）也是一行，`status` 會再說一次。修好原因後要**從頭重走**，兩種做法擇一：
  - 刪掉這次的紀錄再跑：`rm -r /tmp/menu-try/menu/hello`，再打同一個 `run`。
  - 或在 `run` 那行最後加 `--run 新名字`（例 `--run try2`），用新名字另走一份；紀錄放在 `menu/try2/`。訊息裡說「換 --run 重走」就是這個。
- 已經做完的再打一次同一個 `run`：只印同一行「做完」，不會重走、不會再問 AI。
- 玩完整個刪掉：`rm -r /tmp/menu-try`。

**第一次用，到這裡就完成了。** 其他的（`menu.json` 每個欄位怎麼寫、接真 AI、`--help` 裡其他選項）第一次都用不到；要自己寫選單時再看 [ADVANCED.md](ADVANCED.md)。
