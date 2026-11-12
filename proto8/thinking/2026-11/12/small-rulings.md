# small-rulings（11-12）：使用者一次裁完一批待裁小題與「已過時建議結案」清單

← [11-12](README.md)

盤點者把散在 SESSION-LOG、WAIT_USER、各 thinking「留給使用者／待裁」的小題整理成 Q01～Q16 與一份「已過時、建議直接結案」清單，頂層貼給使用者。本檔只留題目一句話、裁定與原話。

## 使用者原話（逐字）

- 「刪不刪：全部都可以刪。Q05:a, Q06:a, Q07:a, Q08:a, Q09:b-都做，除了移除子(兩者不要耦合), Q10:a,Q11:a-剩下以後再說。Q12:a,Q13:a,Q14:a,Q15:a,Q16:a。盛夏都可以直接結案。」
- 頂層讀法：「盛夏」＝「剩下」的錯字，指「已過時、建議結案」那份清單全部結案；Q09＝做「細的定義動作」與「記錄血統」兩項，不做「rm 子之後順手清 stack」（兩者不要耦合）；Q11＝poke 就夠，其餘「以後再說」（不列待辦、不結死）。
- 同日更早：「代定都OK。」（線 K、eca 線）；外部 MCP：「不用。eca本身就能接mcp，等假日在家再來稿」；「kernel等下午，或是假日」。

## 裁定

| 題 | 題目一句話 | 裁定 |
|---|---|---|
| Q01 | 舊建置殘留：WSL `~/repo/aos-tools` 的 `proto8/impls/aos-kernel-llm`、`aos-gate`，Windows 那份的 `proto8/impls/aos-schema`、`inst` | 刪（頂層另派人刪） |
| Q02 | 公司 WSL `/tmp` 各線測試殘留 | 刪（收工時頂層統一刪） |
| Q03 | 公司桌面 `aos-舊版備份-1106`、`aos-舊版備份-1109` 兩個備份夾＋三份 10 月底舊說明頁 | 刪（頂層另派人刪） |
| Q04 | 家機 `proto8/thinking/2026-11/09/local-model-bench/` 與斷捷徑 `~/.local/bin/copy-out` | 刪（家機 session 動手） |
| Q05 | self-system 剩五條代定（[self-system 02](../11/self-system/02-施工結果與代定.md)） | a 都認可 |
| Q06 | 11-10 深夜十幾份代定清單（HANDOFF「2026-11-10 深夜」第 3 點列的各檔）＋線 K K1～K4（[line-k-leftovers](line-k-leftovers.md)） | a 一次認可結案 |
| Q07 | `aos-tools call` 印 `ls: error:` 重現不出來 | a 結案 |
| Q08 | `agents_ctl` 能 rm 別人帳上的子 | a 維持現狀 |
| Q09 | agent_def「之後可加」三項（[agents-split § 之後可加](../10/agents-split/README.md#之後可加)） | b：做「細的定義動作」與「記錄血統」；不做「rm 子之後順手清 stack」，兩者不要耦合 → [agent-def-fine-lineage](agent-def-fine-lineage.md) |
| Q10 | 定義檢查與條文跟實作對不上（eca-claude 報缺檔、`lib/aos/defs` 三個小怪處、C-42、C-52 例外 ⑧） | a 照現在的實作修齊 → [defs-check-align](defs-check-align.md) |
| Q11 | daemon 中斷 poke 之後還做不做（socket、plan 9、搶占） | a poke 就夠，剩下以後再說 |
| Q12 | aos-post／aos-lock 補不補「取」「解鎖」 | a 不補結案（aos-lock 改 flock 照排） |
| Q13 | 固定名字判準的後續想法 | a 沒有了，照 C-51 加註結案 |
| Q14 | 接第三種 CLI pi | a 不做結案 |
| Q15 | tasks（seq／par／if）N-34 草稿 | a 維持「之後順便做」 |
| Q16 | NORMS 待定裡「已照推薦定、只差寫進條文」的四條（函數成長、工具＝函式庫、`_metainfo`、Linux 權限與沙箱） | a 授權照現況落成正式條文（C-55 續、C-61／P-41／P-33／P-25、N-69、C-64／N-41） |
| 剩下 | 「已過時、建議直接結案」清單（下列） | 全部結案 |

「剩下」那份清單：tools_def 之後可加；self-system「codex 叫 self_system 卡兩件」；lift-to-norms 剩次要兩件；json-memory 05 的 D1～D22、11-05 夜「知識庫 CONVENTION 定稿編號」、two-machines B15（都屬 knowledge／memory）；介質兩題；node-pool 想法 21 五題；eca「停著改 history 再繼續」；10-24 沙箱 `accept` 衝突（S18）；10-24 compact 與 P-41；10-15「對話太長」與 WAIT_USER「腦的工具兩題」；KISS 批次 2～6；agents-split「4096 context 裝不下」「`$` 鍵寫不出」；11-10 兩件小事（clock 登記殘留、kernel 範本 budget.senders 警告）；codex 唯讀沙盒對照表沒下結論；效能標準；大修材料「main 有改要同步」；special-cases 剩 4 處條文矛盾；arch-refactor「剩頂層 artifact／桌面 html」。

## `_metainfo` 的後續想法（11-12，今天不做）

- 「metainfo這塊就是搬進去，_index進去後就是index，去掉_。現在先不用做，這是後續想法。_entry確實不能搬進去，所以就是有些能搬有些不能搬，我們就是開了metainfo這個口子，要用不用都可以。json檔案也一樣。_metainfo整合應該會是一兩個禮拜後的事情了。」
- 條文 N-69 只照今天的現況寫，加一句指回 [index](index.md)。

## 11-12 下午再裁三條（agent_def 兩題、沙箱與 C-04）

使用者 11-12 下午原話（逐字）：「執行時誰生的誰不用另外記。空資料夾丟給agent_def check...算他過，風險自己承擔...或者說空資料夾本身當然也算定義。沙箱這個不算硬衝突，daemon處理linux那邊的事，這是推薦，我們所做的各種程式也都盡量遵循，但其他使用者想自己搞其他的當然也可以，風險自己承擔。錯誤路徑那個是細節，後續之後遇到問題再慢慢修，現在先這樣就好，啊json那個可以修。」

| 題 | 裁定 |
|---|---|
| 執行時「誰生的誰」要不要另記（[agent-def-fine-lineage](agent-def-fine-lineage.md#留給使用者的題)） | 不另記，維持現況：父的 `subagents.json` 有、子 rm 掉就消失；定義的血統照舊只記 `agent_def new` 寫的 `lineage` |
| 空資料夾交給 `agent_def check`（[defs-check-align](defs-check-align.md#留給使用者)） | 照樣算過、風險自擔；空資料夾本身也算定義，不另外先確認 `path` 是不是一份定義 |
| 沙箱（aos-sandbox 由呼叫方關、不經 daemon）跟 C-04「daemon 完全處理 Linux 那邊的事」 | 不算硬衝突：C-04 是推薦，aos 自己的程式盡量照它；別人要另搞也可以、風險自擔。只在 [C-04](../../../docs/CONCEPTS/01-設計理念/01-C-01～C-48.md) 與 [C-64](../../../docs/CONCEPTS/01-設計理念/05-布局成長與檔案權限.md#檔案權限10-16-使用者定) 的沙箱段各補一句「是推薦」，別的不改 |

同一段話的後半（錯誤路徑、json）記在 [line-k-leftovers § 錯誤行](line-k-leftovers.md#出錯時的錯誤行不帶絕對路徑11-12-稍後線-errpath)。
