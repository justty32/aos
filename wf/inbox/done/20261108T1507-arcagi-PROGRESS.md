---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T15:07:24+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# r06 收輪：evaluation 56/400（+18、退步 0）；r07 轉元優化

**成績**：evaluation 38→56/400（同大小 14→23/270），training 96→138/400；evaluation 對 r05 與 native-s1 退步 0；每題最長 19.0 秒；入口改混合 native/bin/solve。

**學到什麼**：增量 18 題中 S1 x_* 原語 7、C++ 寬搜尋 5、S3 families 5、主線 n_holes 1——主線三線本身 evaluation 0 增量。再次證明瓶頸在表達力；元優化在固定旋鈕上觸頂（12 設定只有 1 個雙折都贏）。過 train 答錯上升（Python eval 14→17、train 26→30；native 另 12／27），r07 要收。

**程式方法**：A 合成集多數門檻接三台產生器＋雙折 _gen/_meta（extract＋formula）＋meta 帳 aos/meta/ledger.jsonl；B 改寫預設關、attribution.py／intercept.py／eval_r06.sh；C 影子工具 src/arcagi/shadow/＋gen_llm（S2 候選 37 過 11，單題巨集 6 顆 covered）。帳 epoch 6。

**aos 接了**：meta 帳、空基準＋雙折、影子門檻、合成集當真值供給、LLM 產生器進 node-pool（llm_* 分紅）。

**代定**（12 條，notes/rounds/r06/代定清單.md）：主分不跑求解器、S1 邊界（主線定入口與量法）、Argon 採納 4 條（雙折／淨邊際／消融含 pred；改寫預設關＋攔截量測；線 C 可 0 入庫；門檻 >42 單列 Python）、不採納呼叫鏈巨集、主線加 n_holes、LLM 直接解題不算主線分。

**使用者想法進展**：「優化產生積木的過程」做出第一版可量的元優化（雙折、meta 帳）；結論是要改結構不是調參數——正好接 14:55 元優化主軸與 14:58 最終目標。

**支線整合**：S1 x_* 與 C++ 寬樹經混合入口全收；S3 families（7220e25）在工作樹內一起量；S2 候選經影子入庫；S5 合成集軟接進產生器；S4 labels 出每類解題率（reports/dsl-search-r06/rates.csv）。

**下一輪**：主軸元優化——小 training 題組（5～20 題）從空基準學到解出的學習曲線；產積木不經 LLM（library learning、re-arc 確定性程式、殘差診斷、演化）；S2 數字當 LLM 對照基線；S4 池子；收過 train 答錯。詳 notes/rounds/r06/04-總結簡報.md §6。論壇 p-20261108-150706-491f（精華）。
