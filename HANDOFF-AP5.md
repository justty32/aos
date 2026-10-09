# HANDOFF：AP5（學徒自我改進 A／B 對照）

分支 loop13/AP5（未 merge、未 push）。報告草稿：`proto7-2/notes/play/2026-10-09-real-ai/apprentice-5.md`（標「未完成」）。意圖卡：`proto7-2/notes/intents/apprentice-5.md`。

## 做到哪

- 完成並 commit：文字交件格式（`propose --format text`、三關自動辨識）、4 題 mail 題（`examples/aos-tool-mail{count,sent,open,status}`）、審查標準補「以答案檢查器為準」、檢查器「增減」變體。author 測試 166 條全綠（指定子集）。
- **全套 `proto7-2/tests/run_all.py` 還沒跑、還沒 rebase main**。
- 對照實驗：只跑到 4 組（luna／sol-low × A／B）題 1 第 1 輪，全部在第 2 關撞到三條慣例。數字見報告。

## 還剩什麼

1. 試跑 4 組跑完（每組 4 題、每題最多 5 輪；約 30～60 分鐘一組，可 4 組並行）。
2. 挑差異清楚的模型，A、B 各加到 ≥5 次。
3. `compare5.py` 出表、寫報告開頭三行結論（證明／沒證明、差多少、雜訊多少）。
4. rebase main、全套一次、commit。

## 怎麼接著跑

```sh
W=/home/lorkhan/repo/simple_tools/aos-wt/AP5
D=$W/proto7-2/notes/play/2026-10-09-real-ai/evidence/apprentice5
# 1. 學徒 node＋帳本（grant 1 億 token）
N=/tmp/ap5-node; mkdir -p $N/.aos $N/budget/llm
cp /home/lorkhan/repo/simple_tools/aos-wt/apprentice-node/budget/llm/grant.json $N/budget/llm/
echo '{"round":5,"open":false}' > $N/.aos/round.json
cd $N && python3 $W/proto7-2/packs/budget/bin/aos7-budget init budget/llm
nohup python3 $W/proto7-2/packs/budget/bin/aos7-budget ledger budget/llm > $N/ledger.log 2>&1 &
# 2. 跑一組：go.sh 標籤 模型 A|B 次號 rid前綴（不同模型同時跑一定要給不同前綴，否則 call id 撞名）
mkdir -p /tmp/ap5-runs && cp $D/go.sh /tmp/ap5-runs/ && cd /tmp/ap5-runs
for v in A B; do nohup ./go.sh luna chatgpt-gpt-6-luna $v 1 L & nohup ./go.sh sol chatgpt-gpt-6-sol-low $v 1 S & done
# 進度：/tmp/ap5-runs/<組>/drive.log；完成：/tmp/ap5-runs/done.log
# 3. 出表
python3 $D/compare5.py /tmp/ap5-runs/luna-A* /tmp/ap5-runs/luna-B*
```

drive5.py 細節：交件 `--format text`；B 組只有題目沒一次過才 `learn --skill-into`；「慣例命中」＝錯誤訊息出現該慣例標籤（變體失敗時標籤都會出現，會高估，看輪數為主）。

## 目前初步數字

4 組題 1 第 1 輪：全部 ② answer 擋下、三條慣例都出現；第 1 關 4/4 過（無 JSON 手滑）；每輪學徒約 5.6～6.1 千 token。學徒 node 合計 21 次呼叫、134 060 token（含兩次中止的試跑）。

## 注意

- 收工時已停掉所有程序、刪 /tmp/ap5-node 與 /tmp/ap5-runs；舊帳不需要。
- 殺程序別用 `pkill -f drive5`（會殺到自己的 shell），用 `pkill -f "[d]rive5.py"`。
- 代定：文字格式「段頭不能出現在內容裡」只寫成限制、沒做跳脫；四份 check_answer.py 是近乎重複的複本（需求資料夾單獨複製，無法共用模組）。
