← [五家真跑](README.md)｜重算：[rescore-74-75](rescore-74-75.md)｜規則：[spec/team/market.md §3](../../../spec/team/market.md)

# astra 唯讀審查：第 74、75 題（成功率、審查係數）

2026-09-25 晚｜模型 gpt-6-astra（codex CLI，`--sandbox read-only`）｜範圍 `97a2590b..09b57cb6`（7 個 commit：市場排名公式加成功率與審查係數、新子模組 `lib/aos_market_review.py`、`aos_market_grant.rank()`／`aos_market_score` 改動、`test/test_market_review.py`、規格／工作流／文件同步、rescore-74-75）｜指令 `codex exec -m gpt-6-astra --sandbox read-only -C <repo> --color never -o <out> "<prompt>" < /dev/null`，耗時 332 秒｜審查者沒改任何檔；下面的驗證由調度者（Fable）在主 repo 用唯讀 python 重跑一次。

## 驗證摘要（調度者自己跑過）

| # | 必修 | 驗證 | 說明 | 處理 |
|---|---|---|---|---|
| 1 | `aos_market_score.py:236` 兩張董事單時間重疊 → 共用同一張製造單，審查係數算錯 | **已驗證成立**（astra 的重現腳本跑出 `[3, 3]`，應為 `[1, 3]`） | 另查真實資料 `~/tmp/company-market-5/` 五家：董事每張單都在上一張結案後才下，**沒有重疊**，所以 rescore-74-75 的數字不受影響；但董事一次下多張（並行）就會對錯單。 | 處理：commit `6bdd8c12`（製造總機單一對一配給董事的單，配不到記 None＋說明；測試 `test_overlapping_*`、`test_resent_order_same_ask_uses_last`、`test_timed_out_ask_does_not_take_later_order`） |
| 2 | `aos_market_review.py:18` 審查紀錄亂序 → 二次過算成一次過 | **已驗證成立**（腳本跑出 `1`，應為 `2`）；**實務上機率低** | 寫入端 `aos_team_task_machine.py:135` 是照時間 append，正常流程不會亂序；只有手改單子檔才會。不能直接改看 `attempt`（機械驗收沒過也會加 attempt）。 | 處理：commit `21dde530`（照每筆 `at` 排再數，缺時間照原順序；測試 `test_review_records_out_of_order_sorted_by_time`） |
| 3 | `aos_market_grant.py:101、109` 秒數＝0 被當「沒秒數」→ 最快那家快＝0 | **已驗證成立**（a 0 秒、b 1 秒 → b 快 100、a 快 0；撥款 b 2917 萬、a 2083 萬）；**本次改動之前就有** | 真跑裡董事下單到結案同一秒幾乎不會發生，但經理人 `--seconds 0` 手給就會踩到。 | 處理：commit `c0ec20f4`（`is None` 判斷、0 秒＝快 100；測試 `test_zero_seconds_is_fastest`） |

建議第 4 條（rescore 文字兩處數量錯）也查過：表格顯示第 2 輪 c2 是 1/3、不是 2/3；c3、c4 三輪各成 6 張、合計 12 張，不是「八張」——**成立**。

建議五條：處理：commit `470f5a04`（1 規格與 `lib/docs/company.md` 寫明改 `review_factors` 要重新 `score`；2 選「程式對齊規格」：`rank` 看 `review_rounds` 裡的 None，那列寫「成功的 N 張裡有 k 張審查係數當 1.0」，不動檔案結構；3 讀 `market.json` 時檢查 `review_factors`，次數比清單長用最後一個；4 rescore 兩處改對、market.md「沒做的」改成五家已跑；5 測試 `test_config_review_factors_whole_path`、`test_bad_review_factors_clear_error`、`test_rank_warns_partial_missing_review`）。修完用複製的 `~/tmp/company-market-5/` 重跑三輪成績板與排名／撥款：11 列數字、名次、撥款全部不變（真實資料沒有重疊單）。

---

## astra 原文

（連結原本是絕對路徑加行號，收進版控時改成相對路徑；行號留在連結文字裡，指的是審查當時 `09b57cb6` 的行號。）

## 1. 必修

1. **[aos_market_score.py:236](../../../lib/aos_market_score.py)：重疊董事單會共用同一張製造單，導致審查係數算錯。**

   程式只取下單到結案期間「最後一張製造單」，沒有核對製造單屬於哪張董事單。已重現：A 一次過、B 三次過，結果是 `[3, 3]`，應為 `[1, 3]`；平均係數從應有的 **0.7 變成 0.4**，會影響名次、門檻與撥款。

   同名詞條不能解決這個問題：失敗後重下同一題，若舊單遲到的製造工作落在新單期間，也會混用。需要可追溯的董事單 ID／父子關係；無法確定時應走缺紀錄處理。

   唯讀重現，從 repo 根目錄執行；所有假資料都在記憶體：

   ```sh
   PYTHONPATH=proto5/lib python3 -B -c '
   from pathlib import Path
   from unittest.mock import patch
   from contextlib import ExitStack
   import aos_market_score as s

   def at(n): return "2026-09-25T10:%02d:00+08:00" % n
   asks = [dict(id=k, at=at(n), status="REQUEST", **{"from":"human"})
           for k,n in [("A",0),("B",2)]]
   closes = [dict(id=k, at=at(n), status="DONE", text="結論：合格",
                  **{"from":"lead"}) for k,n in [("CA",5),("CB",6)]]
   orders = [
       dict(at=at(1), to={"dept":"mfg"}, task="A"),
       dict(at=at(3), to={"dept":"mfg"}, task="B"),
       dict(at=at(4), to={"dept":"qa"}, status="done")]
   def letters(p):
       if p.name == "human" and p.parent.name == "team": return closes
       return asks if p.name == "done" else []
   with ExitStack() as stack:
       for obj,key,kw in [
           (s.co,"load",dict(return_value={"front":"hq"})),
           (s.co,"host_dept",dict(return_value="hq")),
           (s.co,"team_dirs",dict(return_value={"hq":Path("/virtual")})),
           (Path,"is_dir",dict(return_value=True)),
           (s.fmt,"json_files",dict(return_value=range(3))),
           (s.fmt,"read_json",dict(side_effect=lambda p:orders[p])),
           (s,"_read_letters",dict(side_effect=letters)),
           (s,"_qa_verdict",dict(return_value=None)),
           (s,"_review_rounds",dict(side_effect=lambda ts,o:{"A":1,"B":3}[o["task"]]))]:
           stack.enter_context(patch.object(obj,key,**kw))
       print(s.board_from_company("/virtual")["reviews"])
   '
   ```

   實際輸出：`[3, 3]`。

2. **[aos_market_review.py:18](../../../lib/aos_market_review.py)：審查次數直接使用陣列位置，紀錄亂序會把二次過算成一次過。**

   例如第二次通過的紀錄排在第一次失敗之前，程式直接回傳 `1`，係數從 **0.7 變成 1.0**。缺漏紀錄也沒有核對或警告。不過不能直接改用 `attempt`：機械驗收失敗也會增加 attempt，需對照真正的審查次序。

   唯讀重現：

   ```sh
   PYTHONPATH=proto5/lib python3 -B -c '
   from pathlib import Path
   from unittest.mock import patch
   import aos_market_review as r
   ticket = {"status":"done","review":[
       {"rev":1,"attempt":2,"pass":True},
       {"rev":1,"attempt":1,"pass":False}]}
   with patch.object(r.fmt,"read_json",return_value=ticket):
       print(r._review_rounds({"mfg":Path("/virtual")},
                             {"to":{"dept":"mfg"},"task":"t-1"}))
   '
   ```

   實際輸出：`1`；這份紀錄應辨識為二次審查才過。

3. **[aos_market_grant.py:101](../../../lib/aos_market_grant.py)、[109](../../../lib/aos_market_grant.py)：合法的零秒完成被當成沒有秒數，最快者反而少拿款。**

   `score` 允許秒數為零，但排名用真假值判斷，把零排除。兩家公司成功張數、品質相同，A 用 0 秒、B 用 1 秒，結果 B 快＝100、A 快＝0；只有一家且零秒也違反「無對照快＝100」。這是原有問題，本次修改後仍存在。

   唯讀重現：

   ```sh
   PYTHONPATH=proto5/lib python3 -B -c '
   from aos_market_book import DEFAULT_PARAMS
   from aos_market_grant import rank, plan_grants
   m = dict(params=DEFAULT_PARAMS, history=[],
       companies={n:{"status":"operating"} for n in ("a","b")},
       scores={n:dict(round=1,done=1,failed=0,quality=100,seconds=t,
                      review_factor=1) for n,t in [("a",0),("b",1)]})
   rows = rank(m,{})
   print([(r["name"],r["speed"],r["score"]) for r in rows])
   print(plan_grants(m,rows))
   '
   ```

   實際 A 拿 **20,833,333 token**，較慢的 B 拿 **29,166,666 token**。

## 2. 建議

1. **[aos_market_score.py:282](../../../lib/aos_market_score.py)、[aos_market_grant.py:92](../../../lib/aos_market_grant.py)：文件應寫清楚「改係數後必須重新 score」。**  
   係數在 `score` 時計算並存檔，`rank`／`grant` 不重新讀參數換算；實測二次過係數改成 0.2，品質為 20，再改成 0.9，直接 rank 仍為 20，重新 score 才變 90。這是生效時點未說明，不是設定完全沒接上。

2. **[aos_market_grant.py:105](../../../lib/aos_market_grant.py)、[market.md:52](../../../spec/team/market.md)：新打分的缺審查紀錄警告不會出現在 rank，與規格不符。**  
   `reviews=[None]` 經 score 已存成係數 `1.0`，rank 只檢查係數是否 `None`，又沒有帶入 score 的 `notes`，因此看不出這個 1.0 是預設值；部分缺漏亦同。score 當下的警告有印，計算也正確。

3. **[aos_market_review.py:30](../../../lib/aos_market_review.py)、[aos_market_book.py:90](../../../lib/aos_market_book.py)：可調參數應驗證非空、數字有限及合理範圍。**  
   現在 `review_factors=[]` 到 score 才拋 `IndexError`，負數或大於 1 的係數則能直接進入排名；設定讀入時沒有檢查。

4. **[rescore-74-75.md:39](../../../notes/2026-09-25-company/market-run-5/rescore-74-75.md)、[54](../../../notes/2026-09-25-company/market-run-5/rescore-74-75.md)：解說有兩處數量錯誤。**  
   第 2 輪 c2 成功率是 **1/3**，不是 c2～c4 一起為 2/3；c3、c4 三輪各成功六張，合計 **12 張**，不是八張。因此「三家扣得一樣多」不能成立，雖然本次名次確實沒變。

5. **[test_market_review.py:48](../../../lib/test/test_market_review.py)、[86](../../../lib/test/test_market_review.py)：測試應補重疊訂單、亂序／缺漏紀錄與 config 覆蓋的整條路徑。**  
   現有案例使用分開時段、完整且排序好的 review；成功率測試則直接塞分數，抓不到上面的配對問題。另 [market.md:106](../../../spec/team/market.md) 還寫「沒做五家同跑」，應同步更新。

## 3. 確認沒問題

1. **[aos_market_grant.py:89](../../../lib/aos_market_grant.py)、[100](../../../lib/aos_market_grant.py)：一般輸入的成功率與快的比較群組符合裁決。**  
   品質確實乘 `done/(done+failed)` 與審查係數；快只比較成功張數最多者。已核對成功張數並列時按秒數比較，其餘為零。

2. **[aos_market_grant.py:93](../../../lib/aos_market_grant.py)、[148](../../../lib/aos_market_grant.py)：零張單、全失敗都不會除零，四項分數與預設撥款皆為零。**  
   記憶體測試也確認：只有一家成功且秒數大於零時，快、省都是 100；舊 score 沒有 `reviews`、`review_rounds`、`review_factor`，rank 與 grant dry-run 都能執行，以係數 1.0 計算並註明缺紀錄。

3. **[aos_market_score.py:203](../../../lib/aos_market_score.py)、[207](../../../lib/aos_market_score.py)、[273](../../../lib/aos_market_score.py)：逾時確實加入 failed，成功率分母不會漏掉，也不會把 timeout 再加一次。**  
   唯讀測試得到未結案單 `failed=1, timeout=1`，列入 skip 後兩者歸零；跨輪排除名單由 `timed_out` 傳入。此確認限於訂單配對正確的情況。

4. **[aos_market_review.py:13](../../../lib/aos_market_review.py)、[24](../../../lib/aos_market_review.py)：完整紀錄的一／二／三次係數、FAILED＝0、無紀錄回 None 都正確。**  
   它讀的是父單的 `review`；只要父單紀錄完整，審查子單檔案的列舉順序、甚至子單檔缺失，不影響計算。已執行唯讀 `test_market_review.ReviewFactor`，通過。

5. **[aos_market_book.py:89](../../../lib/aos_market_book.py)、[aos_market_score.py:282](../../../lib/aos_market_score.py)、[aos_market_grant.py:199](../../../lib/aos_market_grant.py)：config 覆蓋的計算路徑確實接通。**  
   路徑是 `market.json.params` 覆蓋預設 → score 換算並平均 → 存入 `review_factor` → rank 調整品質 → grant 按排名及門檻分配；不是只加了一個無效的預設欄位。

6. **[aos_market.py:39](../../../lib/aos_market.py)、[test_market.py:322](../../../lib/test/test_market.py)、[351](../../../lib/test/test_market.py)：此次新增對外 helper 已再匯出，指定測試中的 patch 也打得到實際物件。**  
   新增的 `review_factor` 有匯出；既有對外匯入未被移除。這兩個測試檔沒有 `patch("aos_market.…")` 字串替換，使用的是共享模組物件上的 `patch.object(cost, ...)`、`patch.object(mk.shutil, ...)`、`patch.object(co, ...)`，實測物件相同。若日後 patch `aos_market.board_from_company`，則**不會**替換 score 子模組內的名字，應 patch `aos_market_score.board_from_company`。

7. **[market.md:55](../../../spec/team/market.md)、[market-round.md:9](../../../playbook/workflows/market-round.md)、[docs/company.md:14](../../../lib/docs/company.md)：三份文件的主要公式與「只在最多成功張數者比快」一致。**  
   差異是前述缺紀錄警告、生效時點與零秒邊界，不是權重或主要公式寫反。

8. **[rescore-74-75.md:26](../../../notes/2026-09-25-company/market-run-5/rescore-74-75.md)：第 1 輪 c2 的新分數 70.59 重算正確。**  
   原始資料審查為 `[1,3,1]`，係數 `(1+0.4+1)/3=0.8`；品質 `100×1×0.8=80`。快 `round(221/329.7×100,2)=67.03`，省 38.90；總分 `round(80×0.6+67.03×0.25+38.90×0.15,2)=70.59`。

9. **[rescore-74-75.md:27](../../../notes/2026-09-25-company/market-run-5/rescore-74-75.md)：第 1 輪 c5 的品質 21.34、總分 15.77 重算正確。**  
   按程式精度，品質 `round(91.45×0.3333×0.7,2)=21.34`；成功張數少，快＝0；省 `round(2514718/12716165×100,2)=19.78`。總分 `round(21.34×0.6+19.78×0.15,2)=15.77`。

10. **[rescore-74-75.md:29](../../../notes/2026-09-25-company/market-run-5/rescore-74-75.md)、[53](../../../notes/2026-09-25-company/market-run-5/rescore-74-75.md)：第 2 輪 c3 的 78.70，以及本次三輪名次、token 撥款不變，都重算吻合。**  
    c3 品質 `100×0.6667=66.67`；快改與 c4 比，`round(209.5/221×100,2)=94.80`；省＝100；總分 `round(66.67×0.6+94.8×0.25+100×0.15,2)=78.70`。我用原始資料、在記憶體依各輪 grant 時間截斷信件，重跑全部 **11 筆**參與排名的紀錄，分數及 token 撥款均與報告／history 相符。

結論：主要公式與本次重算表正確，但有三項必修：重疊單錯配、亂序審查誤算、零秒完成被扣快分。  
config 有接上，改值後須重新 score；舊分數資料可繼續 rank／grant。  
全程未修改檔案；未跑會建立暫存檔的整套測試，因此不替「2881 條全綠」背書。