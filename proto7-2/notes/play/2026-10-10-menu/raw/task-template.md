你是第一次用 aos 的新手，什麼都不懂。你只能讀一份文件：/home/lorkhan/repo/simple_tools/aos-wt/MN4/proto7-2/packs/menu/README.md（aos 資料夾就是 /home/lorkhan/repo/simple_tools/aos-wt/MN4）。不要讀其他任何 .md（ADVANCED.md、spec.md 也不要）、不要看原始碼（.py）、可以跑 `--help`。不要改 repo 裡任何檔；要改東西就先複製到你自己的資料夾再改。不要動不是你開的程序。

規則：文件裡所有 /tmp/menu-try 一律換成 WORK（=/tmp/mn4-play/WHO/ROUND/menu-try），免得和別人撞。你自己的暫存檔都放 /tmp/mn4-play/WHO/ROUND/ 底下。

照做：
1. 照 README「第一次跑」跑起來，看 out/ 寫了什麼。
2. 故意弄壞，每項記下你打的指令與印出的那行，判斷看不看得懂、知不知道怎麼修：
   a. 給一個不存在的資料夾當第一個參數去 run。
   b. 把 examples/hello/ 整個資料夾複製到 /tmp/mn4-play/WHO/ROUND/my/，在你的複本 menu.json 裡把 "who" 那層的 "exit" 整段刪掉，用你的複本跑 run（第一個參數用新的空資料夾）。
   c. 再複製一份乾淨的 hello，把複本的 practice.json 改成只剩第一句，用新的空資料夾跑 run，再跑 status。
   d. 在乾淨 hello 已經做完的 WORK 上，再跑一次同一個 run；然後照 README 讓它從頭再走一次。
3. 收掉：照 README 把 WORK 刪掉。

最後回報（純文字，直接寫在最終回覆，不要寫檔）：
A. 每一步實際打的指令與印出的原文。
B. 五題：(1) AI 每次看到什麼？它要怎麼回答？（2）「練習用的 AI」是什麼？花不花錢？為什麼範例裡有一次被要求重回？(3) hello 選單的三層各做了什麼？寫出來的東西放在哪？(4) 每層最後一個編號是什麼？AI 選了它會怎樣？(5) 想從頭再走一次要怎麼做？對已經做完的再打一次同一個 run 會怎樣？
C. 數一數：第一次跑用了幾個指令（不算 cd、mkdir、cat、rm）？你需要先懂幾個新概念？列出來。
D. 照五條標準各打 1～10 分並舉例：容易上手、容易理解、複雜的藏起來、外層控制結構簡單但全面、要背的少。再給一個總分（五條平均）。逐條列出扣分點：哪一行、哪個字讓你看不懂、要猜、嚇人或太長。
E. 一句話：ELI5 之後，這東西複雜嗎？
