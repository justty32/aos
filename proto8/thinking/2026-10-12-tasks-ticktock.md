# 2026-10-12 tasks 與 tick-tock

← [討論紀錄](README.md)

> 10-12 夜照使用者要求精簡成「原文整理、決定、結論」；AI 的調查表、被推翻的選項已拿掉，舊版見 git（commit 22285099）。

## 1. 使用者原文（整理）

**tasks**
- tasks 跟 daemon 的 save 是兩碼事，save 是語法糖。tasks「更像是 lisp 的一些基礎函數」。
- tasks 跟 aos inst 一樣是獨立程式，在 aos inst 的基礎之上：daemon 跑 inst.json，argv[0] 就是它。「tasks 這類只是別名，搞不好還會有 aos-seq 啥的。」指示詞只負責把大 JSON 拆成小檔，跟這個無關。
- 10-12 傍晚補：「aos seq 那些流程控制的東西，很多其實都是不必要的，因為我們可以用普通程式去寫更複雜的邏輯。之所以要做這塊，只是可能會常用，所以先簡單弄一弄。但是到後續，搞不好大家就乾脆一個程式跑下去，控制流都在 argv[0] 的那個程式裡面。」

**tick-tock**
- 「就甲。乙這邊保證打包這件事，應該是後續大家要遵守的規範，不強制。」「打包這塊應該在後續 kernel 那邊做。」（甲＝tick-tock 只是時鐘：daemon 定時跑一支把數字加一的程式，大家抬頭看，不保證打包。）
- kernel 怎麼做打包的例子：「可能就是 kernel 在公告欄說：大家，咱們第 1021 回合準備關機下線，在那之前所有人把狀態保存到檔案，逾時不候。」

**規範比實作重要**（10-12 傍晚）
- 「對，比起實作，更重要的是規範。我們會提供一些符合規範的，方便的語法糖，但不要求所有人一定要使用。好比說 aos 時空這條概念，衍生出的規範就是大家都要看 tick tock 時鐘，還有資料夾別亂弄。」

## 2. 決定

**tasks**（已做，在 [proto8-1](../../proto8-1/README.md)）
- 只做最精簡的四支：seq、par、if、not；不管 daemon。不再加 while／retry。
- loop／daemon 狀態加 `last_code`；daemon 自己的退出碼不改。
- 結束碼的規矩以同夜的 [inst 進 json](2026-10-12-inst-json.md) 為準（inst 只回自己的碼，子程式的碼進 exit 檔）。
- demo 的 15 條發現在 [proto8-1/demo](../../proto8-1/demo/README.md)，使用者說「都按照建議」。

**tick-tock**：選甲 → CONCEPTS C-44。照 AI 提的規格，使用者說「做吧」：
- tick＝回合數加一，就是 `aos-tick`；tock 不另外做。
- `aos-tick FILE`：讀 n 寫 n＋1（十進位＋換行），先寫暫存再改名。
- 節奏、停、只走 N 回合交給 daemon（`interval_ms`、pause／resume、`times`）。
- 訂閱＝抬頭讀時鐘檔，不需要名單；mtime＝這回合從什麼時候開始。
- 甲不包任務，所以「中間任務失敗那回合算什麼、要不要 finally」這題不存在；finally 不做。

**規範比實作重要** → CONCEPTS C-45，開 [NORMS](../NORMS.md)。使用者說「對」的那份清單：任何 argv[0] 程式都要守的規矩——結束碼（只有 0／非 0 是慣例）、收到 SIGTERM 收好子程式、不 setsid 跑出群組、錯誤寫 stderr。

## 3. 未決

- 要不要「等到第 N 回合」的小程式：等真的有 node 要用再說。
