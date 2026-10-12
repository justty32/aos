# 2026-10-12 tasks 與 tick-tock

← [討論紀錄](README.md)

## 1. tasks（使用者說的，已做）

- tasks 跟 daemon 的 save 是兩碼事，save 是語法糖。tasks「更像是 lisp 的一些基礎函數」。
- tasks 跟 aos inst 一樣是獨立程式，在 aos inst 的基礎之上：daemon 跑 inst.json，argv[0] 就是它。「tasks 這類只是別名，搞不好還會有 aos-seq 啥的。」指示詞只負責把大 JSON 拆成小檔，跟這個無關。
- 只做最精簡的：seq、par、if、not，放在 [proto8-1](../../proto8-1/README.md)。不管 daemon。
- 結束碼因此變得重要：aos_inst 命令列回子程式的碼；自己出錯 127／126／125；loop／daemon 加 `last_code`；daemon 自己的退出碼不改。
- demo（AI 編的場景）寫起來的 15 條發現在 [proto8-1/demo](../../proto8-1/demo/README.md)；使用者說「都按照建議」。

## 2. tick-tock：過去的作用、剝掉跑任務之後剩什麼（AI 調查，事實）

過去各代（proto6、7、7-1、7-2、core/tick）tick／tock 都是「跑任務」（A）和「時間」（B）綁在一起；7-2 的 tick 414 行、tock 198 行，大半是 A。

剝掉 A 剩下的 B：

| B | 過去 | proto8 現在 |
|---|---|---|
| 時間＝回合、計數、重開接續 | 6、7、7-1、7-2 | daemon 的 `runs` 像，但只在記憶體 |
| 節奏：固定 interval／提前 tock | 7-1、7-2 | 只有「跑完再隔 interval」 |
| 讓時間停：擋板、pause、倒數、wake | 6、7-x | daemon pause／resume；倒數、wake 沒有 |
| 通知回合開始／結束 | 7-x（tock.json 寫給活任務） | 沒有 |
| 一致性、互斥（舊回合關了才開新的、鎖、世代） | 7-1、7-2 | loop 同一實例不重疊，自然成立 |
| 每回合紀錄 | 6、7-1、7-2 | 沒有 |
| 「tick 之間可以安全打包」 | **沒有一代做過** | 只有使用者提過（2.11、3g.5） |

剝掉後會懸空的（過去靠 A 撐著）：
1. 回合何時結束——過去都是「任務跑完」或「時間到」。
2. 通知寫給誰——過去是 tick 起過的任務；「node 訂閱」沒有名單或位址。
3. 紀錄記什麼——過去幾乎全是任務資訊。
4. 打包為什麼安全——proto6 安全是因為 tick 同步跑完所有任務；7 以後任務跨回合，邊界上本來就不穩。要成立得有人保證「回合之間沒人在寫」，那就又變回管任務。
5. pause 的意思——過去＝tick 不起任務；剝掉後只剩「不往下數」。

AI 的觀察：剝乾淨的 tick-tock 很小（一個往上數的數字＋節奏＋可選的通知），節奏、暫停、不重疊 daemon 已經有。關鍵在第 4 點：要「打包安全」就得有人管寫的人；不要的話 tick-tock 就只是時鐘，安全由各 node 自己負責。

## 3. 還沒定

- 使用者：「tick tock 這邊我想想……」
- AI 先前列的兩題：tick、tock 各自做什麼；中間任務失敗那回合算什麼（tock 要不要一定跑＝需不需要 finally）。
