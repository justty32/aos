# round6 示範：漂移（真腦，10-25）

← [round6 §5、§7 第 7 項](../../round6.md)｜程式 [train/score/drift.py](../../../train/score/drift.py)（score 每輪寫 `rounds/<輪>.json.drift`）、[train/init](../../../train/init/_entry)（存錨點）｜數字 [arbiter/rounds_summary.json](arbiter/rounds_summary.json) 的 `2.drift`、基準 [arbiter/drift_baseline.json](arbiter/drift_baseline.json)｜測試 `ArbiterOptimize.test_optimize_two_candidates_arbiter_apply_drift`（假腦全 0）

## 錨點（train/init 第一次建訓練場時存，之後不動）

`tree_v0/`（那時的樹）、`critic_v0/`（那時的 judge/tools/critic）、`v0_drafts/`（A 段基準 [round4/round0](../round4/round0/) 的稿，tree_v0 那一代的既有稿）。

## 三條線（向量＝critic 的 semantic÷3、承接、含蓄、角色味、反差、文筆；值＝各稿各維差的平均）

| 線 | 怎麼算 | 第 2 輪 | token |
|---|---|---|---|
| ① critic 漂多少 | 現在的 critic 評 v0 稿 − critic_v0 評同一批 v0 稿 | **0**（critic 檔案 hash 與 critic_v0 相同：「critic 未變＝漂移 0」，沒問腦） | 0 |
| ② 樹真的進步多少 | critic_v0 評這輪的稿 − critic_v0 評同題 v0 稿（基準） | **−0.063**（2 稿：主角先的兩題；含蓄 −0.10、反差 −0.10、semantic −0.08、承接／角色味 −0.05、文筆 0） | 7,308（基準 2 次）＋7,170（這輪 2 稿）＝14,478 |
| ② 旁：critic_gap | 這輪 score.json 裡 critic 給的 − critic_v0 給同一稿的 | 0.008（承接 +0.15、角色味 −0.10…）＝同一把尺評兩次的雜訊 | （同上） |
| ③ 有錨 vs 無錨 | 跟上一輪比：lint 維（護欄、語域）平均變化 vs critic 維平均變化 | lint 0、critic −0.033；同升同降 false、suspicious false | 0 |

## 怎麼讀

- **critic 這輪沒變**，所以①是 0、不花錢；它只在有人改了 critic（system.txt、ask.py）之後才會問腦（拿現在的 critic 評 v0 稿）。
- **②的 −0.063 不當結論**：只有 2 稿，而 critic_gap（同一把尺、同一稿評兩次）各維就有 ±0.1～0.15 的差——②的量級在 critic 自己的雜訊裡。要讓②有意義，稿數要多（4 稿以上）或同稿多評幾次取平均。
- **基準有一格是 2.5 分**：critic_v0 評 v0「主角先_集章冊」給 semantic 2.5（0.83），比整數尺細；這讓 semantic 那維看起來掉了 0.08。尺本身允許小數。
- ③這輪 lint 維沒動（兩輪都滿分）、critic 維略降：不是「critic 升而 lint 沒升」那種可疑型。lint 維在這個場景已經頂到天花板，它當錨只能抓「變壞」，抓不到「變好」。
- 假腦：基準、這輪、critic_gap 全是假腦的固定分 → 三條線全 0（測試釘住）。

## 代定

- 基準（critic_v0 評 v0 稿）每題只問一次，存 `$AOS_WS/drift/baseline.json`，之後的輪照用；不直接用 round4 當時存的分數，因為那是更早的 critic 打的（不一定等於 critic_v0），會把「尺換過」混進「樹進步」。
- v0 稿的題目借這輪同題的 critic 題目檔（`.stack/critic/ws/done/1.json`）、換掉 draft——場景凍結，所以同題的場景、人物要點一樣。
- 這輪的稿取前 2 份（`round.json` 的 `drift_drafts` 可改）；第 1 輪是搬來的量測組（沒有 .stack），②算不出來（`counter_drafts` 0）。
