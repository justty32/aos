# 05 小實驗（sol，11-07 午）

一句話：五個一小時內的小實驗交 codex `gpt-6.1-sol` 跑完（約 11 分鐘）：歷史累積確實讓 token 翻倍、腳本填 sources 可以把來源錯清乾淨、溫度 0 救不了重跑一致，另挖出三條新不足。

← [arknights-kb](README.md)

- 實驗書由隊長（opus）定，codex 只照做；原始紀錄在試驗場 `~/code/playground-ak/exp/sol-1107/`（`report.txt`），試驗場 commit `c74723f04`。
- 沒改 proto8 本體、沒碰 `~/code/playground`、arknights repo 唯讀；收尾核對殘留程序 0。

## E1　不足 #2：對已停的 agent listen 會白等到逾時嗎
- 假設：stopped agent 的 `listen --timeout-s 10` 會等滿 10 秒。
- 結果：**沒做成**。agent 根本停不下來：`aos-agent ctl stop` 0.03 秒就退 1，報 `CtlMissing … an exec type can only run and be removed`，agent 仍 running，之後 listen 3.4 秒就拿到答案。
- 白話：這次**沒帶 `--limits`** 也停不了，所以 #2 沒驗到，反而發現 #11 的範圍比原本以為的大。
- 對不足清單：新增 #15（#11 擴大）；#2 仍待驗（要先有能停的 agent）。

## E2　代定 6 ①：sources／標題改由腳本填
- 假設：腳本照 `allowed_sources` 決定性覆寫 `sources:`，`SourceMissing` 歸 0、40 篇全過 lint。
- 結果：**是**。第一輪 40 篇副本填前填後都 40/40；故意塞一篇 `corpus/arknights/evidence/x.md` 的對照組由 39/40 改正為 40/40。
- 白話：腳本填來源這招有效，能直接取代 #9、#14 那種「提示詞叫 LLM 照抄」的繞法。要注意第一輪正式產物本來就沒來源錯（錯的是被閘門擋掉的重派批），所以真正的效益要在第二輪「LLM 只寫本文」時量首敗率。
- 對不足清單：#9、#14 有了可行修法方向（試驗場層，不改本體）；第二輪照代定 6 ① 做。

## E3　不足 #12：歷史累積是不是 token 增長的原因
- 假設：同一題，在「新實例第 1 題」和「同實例第 6 題」token 差 ≥2 倍。
- 結果：**是**（單次對照）。佩爾多尼朵拉（原文 428 bytes）：新實例 10,437 tokens；做過 5 題後的第 6 題 22,660 tokens，2.17 倍，兩邊都是 3 calls。前五題依序 10,663 → 13,106 → 15,597 → 17,901 → 20,412，每題約多 2,500。
- 白話：每多做一題，下一題就多背約 2,500 tokens 的舊帳；題目本身只要約 1 萬。每節乾淨上下文（代定 6 ②）一做，token／節點就能回到約 1 萬。
- 對不足清單：#12 從「推論」升為「已隔離驗證」。

## E4　不足 #1：缺 `LITELLM_KEY` 時多晚才炸
- 假設：起樹全程無警告，第一問才 `EndpointFailed`，agent 停在 stopped。
- 結果：**部分是**。起樹 0.35 秒完成、沒提到金鑰（倒是出現 `AOS_TICK points to a missing file` 警告）；第一問才 `EndpointFailed`（對）；但 agent **不是停在 stopped，而是整列消失**，查狀態報 `InstanceMissing`。
- 最小修法原型：試驗場 `preflight.sh` 在起樹前查範本用到的 `--key-env` 變數，缺就退 1 並印 `missing environment variable(s): LITELLM_KEY`，有設就放行。兩種情況都驗過。
- 白話：「起樹前檢查」這招可行又便宜；本體要不要加由隊長另定。
- 對不足清單：#1 描述更正（列消失而非 stopped）；新增 #16（診斷不一致）、#17（新樹就有 AOS_TICK 警告）。

## E5　代定 6 ③：溫度 0 能不能讓重跑相同
- 假設：LiteLLM 接受 `temperature: 0`，且溫度 0 下同 prompt 重複的次數比預設多。
- 結果：**接受是、更一致否**。直接 curl 預設溫度 3 次、溫度 0 三次，全 HTTP 200，兩組都是 3 種不同輸出，相同 0/3。kernel 有口子：`endpoint.fixed.temperature` 在 `llm_http/_entry` 51～57 行合進請求，而 `gpt-luna-low` **本來就固定溫度 0**。
- 白話：第一輪「重跑相同 0%」本來就是在溫度 0 下跑出來的；這個模型溫度 0 也不保證同輸出。要重跑一致只能靠縮窄 LLM 的活（E2 那種腳本化）或比對時忽略措辭，溫度這條可以收掉。
- 對不足清單：無新增；代定 6 ③ 結論＝已是溫度 0、無效。
