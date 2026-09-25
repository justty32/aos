← [HR 部報告](README.md)

# 唯讀審查任務書：HR 部（2026-09-25）

你是唯讀審查員。**不要改任何檔、不要跑會叫模型的東西、不要碰 localhost:1234／LM Studio／ollama**。可以跑單元測試：
`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test.test_team_hr -v`。

## 看什麼

- 規格 `proto5/spec/team/hr.md`
- 程式 `proto5/lib/aos_team_hr.py`；接點 `proto5/lib/aos_team.py` 的 `_hr_home`／`_hr_gate`（init、start）、`proto5/lib/aos_team_spawn.py` 的 `check()` 結尾（cpu 擋點）與 `realize()`（生出來寫 `employment: temp`）、`proto5/lib/aos_team_format.py` 的 `employment` 驗證、`proto5/lib/aos_team_cli.py` 的 `hr` 一行
- 例子 `proto5/examples/hr/ex1/`（任務集、評分指令 `score.py`）
- 測試 `proto5/lib/test/test_team_hr.py`

## 重點問題

1. **試用不動原團隊**：`trial()` 有沒有任何路徑寫到原團隊資料夾或原專案？（`register_team` 寫的是 HR 家的 `teams.json`，算不算？）
2. **調薪規則**（`verdict()`）：基準怎麼挑（同位子、同任務集、強、機械全過、最近一次）；「通過」時什麼情況會把 `min_pass` 換成更貴的？有沒有把 `mech_ok` 跟單子沒 done 混在一起的漏洞？
3. **人頭與 cpu 擋點**：`check_regular` 算「換成新名冊之後」的總數對不對（自己這隊不能算兩次）？試用副本（`AOS_HR_TRIAL`）真的不算人頭？沒 HR 家時一定不擋？擋點會不會讓既有的 init／start／spawn 在沒設 HR 的測試環境行為改變？
4. **`hr set`**：改名冊拿名冊鎖；改家的 `info.json` 沒拿鎖，跟 agent 自己 tick 寫 info.json 會不會打架？重啟順序對嗎？
5. **評分指令**：最後一行不是 JSON、退非 0、逾時各會記成什麼？`score` 是 bool 會被當成數字嗎？
6. 規格跟程式哪裡對不上；白話有沒有講不清楚的地方。

## 回報格式

分三段：**必修**（會錯、會漏、跟規格矛盾，每條附檔案:行號與一句怎麼修）、**建議**、**不用改但值得記下**。總長 1500 字內，中文白話。
