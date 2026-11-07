# 問答 agent 原型：在 ~/code/playground-qa 用 aos 搭一隻附出處回答 arknights 問題的 agent，10 題實測答對 90%、出處對 90%、每題平均約 1.6 萬 token

← [arknights-kb](README.md)｜起因：README 末段「使用者裁定」第 1 題（給人看的走附屬庫或問答 agent，類似 RAG）

## 設計（隊長定、codex gpt-6.1-sol 照做）
- 試驗場 `~/code/playground-qa/`（自己一個 git，最終 commit `ac27448b5`）；aos repo、playground-ak、arknights 語料都唯讀。
- **只用確定性檢索、領域窄**：兩個根——`kb:`（playground-ak 第一輪生成的知識節點）和 `lore:`（arknights `lore/`，不含 evidence）。工具兩支：`kb_search`（ripgrep 固定字串＋別名表先對到節點，最多 12 筆、3 KB）、`kb_read`（只准讀兩根，一次 4 KB）。
- agent `qa_ak`：只依讀到的原文回答、繁中白話、每個論點附 `kb:`／`lore:` 路徑、查不到就說找不到、最多 6 次工具呼叫。
- **每題新開 agent 實例**（避開第一輪不足 #12 歷史累積），腦 `gpt-luna-low` 經 llm kernel。入口 `run/ask.sh "<問題>"`。
- 定義 9 個：`qa_ak`、`kb_search`、`kb_read`、`corpus_common`、`llm_main`、`root_daemon`、`worker_daemon`、`tree_ctl`、`defs_index`，各附白話 README。

## 實測（10 題先凍結 commit 再跑，各跑一次）
配比：5 題 places、2 題 characters／factions（只在 lore）、1 題跨兩檔、1 題繁簡交錯、1 題資料裡沒有。

| 數 | 值 |
|---|---|
| 答對率（部分算半） | 90%（8 對、2 部分） |
| 出處正確率 | 90%（含正確拒答；有引用的 9 題中 8 題對） |
| 每題 token | 平均 15,762、最大 33,325、最小 8,804 |

錯的兩題：05 高盧漏了「地塊瓜分」要點（部分）；07 公證所／奧倫把教廷與公證所立場混了（部分、出處錯）。兩題也是 token 最多的（22.5k、33.3k），查得越久越容易混。繁簡交錯題答對、查無資料題正確拒答。逐題紀錄與報告在 playground-qa 的 `runs/1/`。

## 得失
- 得：不用向量庫、只靠 grep＋讀檔＋別名表，窄領域就有九成；「每題新實例」讓 token 穩在 1 萬上下，沒有第一輪那種越跑越多。
- 得：照原文存＋問答 agent 這條路可行，「原文保意、給人看靠 agent 轉白話」不用另做翻譯庫也能先頂著。
- 失：多實體、立場類題（07）會混；樣本只有 10 題、各跑一次，數字只是第一個基線。
- 失：aos 本體要自己接不少線（見下），試驗場在本地繞過。

## 發現的 aos 不足（已追加到[不足清單](不足清單.md) #18～#22）
1. 收信時 usage 丟掉、記帳比回覆晚到——每題 token 要另外核帳。
2. agent 歷史預設累積（同 #12），要每題開新實例才乾淨。
3. 沒有每題／每次任務的工具呼叫上限，只能寫在 prompt 裡。
4. 掛外部語料（外搬尋址）要自己接 symlink 與路徑白名單。
5. 非同步掛上（送題後等回覆）與程序收尾要自己寫。

## 下一步（給使用者挑）
- 擴題庫到 30～50 題、每題跑兩次看穩定度；07 類題試讓 agent 先列實體再答。
- 附屬白話庫和問答 agent 二選一或並行，由使用者定。
