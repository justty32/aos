你是第一次用 aos 的新手，什麼都不懂。你只能讀一份文件：/home/lorkhan/repo/simple_tools/aos-wt/ST3/proto7-2/QUICKSTART.md（aos 資料夾就是 /home/lorkhan/repo/simple_tools/aos-wt/ST3）。不要讀其他任何 .md、不要看原始碼、不要翻 node 資料夾裡的檔（除了下面第 4 步要你看的信）。不要改任何 repo 裡的檔。不要動不是你開的程序。

規則：文件裡所有 /tmp/aos 一律換成 HOUSE（例如 /tmp/aos/bob 換成 HOUSE/bob），免得和別人撞。你只有一個 shell：「指令 1」要開著，請放背景跑（例如 `setsid -f sh -c '<指令 1> > HOUSE.log 2>&1'`）；要「在視窗 1 按 Ctrl-C」時，改用 `python3 /home/lorkhan/repo/simple_tools/aos-wt/ST3/proto7-2/modules/up/aos7-up stop HOUSE/bob` 代替。alias 在非互動 shell 可能不生效，可以直接打 alias 右邊那串。

照做：
1. 照 QUICKSTART 起 bob、寄一封你自己想的信、跑 status。
2. 用你自己的話解釋 status 每一行在說什麼。
3. 跑 `/tmp/st3-trial/make_stuck.sh HOUSE/bob`（它模擬一次當機：問 AI 問到一半被打斷；跑完心跳在背景另外重開了），然後跑 status，直到出現「卡住了」那行（每 10 秒一次，最多 40 秒）。解釋：發生什麼事？你要不要動手？bob 總共收到幾封信、回了幾封、正在辦幾封？
4. 照那行說的時間等滿再多 15 秒（最多等 90 秒）（用 sleep 分次等），再跑一次 status，解釋現在怎樣；status 說你的信箱有信的話，照 QUICKSTART／status 給的位置打開看一下。
5. 照 status 最後一行把東西收掉，確認 HOUSE 不見了。

最後回報（純文字，直接寫在最終回覆，不要寫檔）：
A. 每一步實際看到的 status 原文。
B. 這五題的答案：(1) 第一次 status 時 bob 收到幾封信、回了幾封？(2) 卡住那時你該做什麼？要等多久？(3)「假 AI」是什麼意思？bob 跟 node 是什麼關係？(4)「心跳」那行在說什麼？(5) 怎麼把全部收掉？
C. 給「只看 QUICKSTART、看懂 status 輸出」打易懂度分數 1～10（10＝完全不用猜），並逐條列出扣分點：哪一行、哪個字讓你看不懂或要猜、覺得嚇人或太長。因為你只有一個 shell 而必須換的作法（背景跑、stop、改路徑）不算扣分。另外，信件內容（第 4 步打開的信）有看不懂的也另列，但不算進分數。
D. 一句話：ELI5 之後，這東西複雜嗎？
