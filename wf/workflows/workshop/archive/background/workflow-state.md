# 名詞表：工作流狀態與格式契約
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### front matter（Markdown 檔頭欄位）

**白話**：在 Markdown 正文最前面放一小塊固定欄位，讓人照樣讀文章，程式也能穩定讀到編號、擁有者、狀態。
**嚴格**：位於 Markdown document body 之前的 machine-readable metadata block，常用 YAML/TOML/JSON 形式，可表達 `id`、`owner`、`workflow`、`resume`等，但不應複製正文政策。
**在 aos 裡具體是什麼**：`wf/open/*.md` 真源目前不存在，是 workflows 候選；現有 `SESSION-LOG.md` 與 `WAIT_USER.md` 沒有這種 task front matter。
**為什麼會冒出這個詞**：[workflows 場](../records/workflows-on-aos.md) 的研究者想讓 open 狀態可讀、可 Git diff 且可跨機，因此用 front matter 承擔機器欄位。

### single source of truth（唯一真源）、generated view 與 drift

**白話**：同一件事只有一處算數；其他畫面都是從它重畫出來的，不然兩邊各改就會對不上。
**嚴格**：canonical state 是唯一允許定義事實的表示；generated view 是可重建的衍生呈現；drift 是多份可編輯表示在沒有單一交易／reconcile 下產生不一致。
**在 aos 裡具體是什麼**：workflows 尚未選 `.aos/wf/*.json` 或 `wf/open/*.md` 當真源；`status --format md` 是 generated view 提案，現有 `SESSION-LOG.md`/`WAIT_USER.md` 仍由人直接編輯。
**為什麼會冒出這個詞**：[workflows 場](../records/workflows-on-aos.md) 發現如果 JSON 與 Markdown 都可改，就會重新形成兩份相衝突的真相。

### reconcile（對帳／修復對齊）

**白話**：中間斷過後，把現在所有憑據排在一起，找出哪些已經算數、哪些只做一半、哪些還差最後一步。
**嚴格**：依耐久 evidence 比對 event、cursor、receipt、effect state 與 next delivery，再以冪等操作補齊或標示人工處理的 recovery procedure。
**在 aos 裡具體是什麼**：目前沒有通用 reconcile 命令；agent loop 與 workflows 都有候選，但尚不知道能否在不理解 turn/final 或 Markdown 政策的情況下通用化。
**為什麼會冒出這個詞**：[agent loop 場](../records/agent-loop-architecture.md) 的開發者指出 crash 後必須對齊四種證據；[workflows 場](../records/workflows-on-aos.md) 又遇到可編輯檔與衍生 view 的反向同步問題。

### ABI、schema、golden files 與 conformance

**白話**：schema 說「一份資料可以長什麼樣」；ABI 說「大家要穩定照哪些規則互接」；golden files 是已知正確範例，conformance 則是拿實作去考這些範例。
**嚴格**：schema 定義資料結構與驗證約束；這裡的磁碟 ABI 是外部實作可依賴的版面、命名、狀態轉換與原子邊界；golden files/conformance suite 驗證不共用 lib 的實作是否讀寫一致。
**在 aos 裡具體是什麼**：instruction schema 與 `.aos` 規格已存在；新 Deliver/MCP 要共用 parser 還未實作；外部處理器的 golden files/conformance CLI 目前不存在。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md) 的開發者指出「不引用 aos lib 也接得上」若沒有一致性測試就只是宣稱。

### JSON Pointer（JSON 內的位置）

**白話**：像文件裡的門牌；`/1/argv/0` 就是「第二筆裡的 `argv`，再往裡數第一格」。
**嚴格**：用斜線分段指出 JSON 值所在位置的字串；陣列位置從 0 起算，物件欄位以名稱表示。
**在 aos 裡具體是什麼**：目前沒有公開契約；Deliver 黑客松第 1 輪提案用 `/1/argv/0` 指出第二筆指令的第一個參數錯誤，現有 `read_all()` 只回報第幾筆。
**為什麼會冒出這個詞**：[Deliver 契約黑客松第 1 輪](../../hackathon/records/deliver-contract.md)要求機器能指出批次裡究竟是哪一格寫錯，而不只回一句「格式不對」。

### template、source version、base hash、three-way diff 與 doctor

**白話**：template 是當初複製過來的骨架；source/base 記得「當初拿的是哪版」；三方比對把當初、上游新版、本地改動一起看；doctor 只找壞掉的地方。
**嚴格**：source version/base hash 定位 installed ancestor；three-way merge/diff 用 base、upstream-new、local 區分上游變更與本地客製；doctor 是不寫入的完整性診斷，可掃 placeholder、壞連結與孤兒路由。
**在 aos 裡具體是什麼**：`wf/` 是已安裝且大量客製的 workflows 實例，但目前沒有上游版本記錄、upgrade 或 doctor 命令；都是 module 候選。
**為什麼會冒出這個詞**：[workflows 場](../records/workflows-on-aos.md) 四位推測安裝／升級可能才是不好用的地方，但也明說這仍是推論，得先問使用者是否真想追上游。


### plumbing 與 porcelain（兩個入口，哪一份是正本）

**白話**：git 有一批給人打的漂亮指令（`git commit`）和一批給程式組合用的粗管子；關鍵是——漂亮指令的內部從來不去叫那些粗管子，它直接呼叫函式，所以粗管子壞掉不會連漂亮指令一起壞。
**嚴格**：同一份實作同時暴露函式介面與命令列介面時，兩者形成兩份必須永遠同義的公開契約；穩定做法是明文指定其中一份為正本（argv 只是函式語意的投影，分歧時函式贏），命令列端只當薄殼，錯誤路徑的測試留在函式那一層。
**在 aos 裡具體是什麼**：目前只有函式一份契約（`core/inst/include/aos/inst.h`），沒有 argv 入口，所以還沒有正本問題；「同一份實作、兩個入口」與「規格明寫哪一份是正本」都是**提案**。
**為什麼會冒出這個詞**：[純 CPU 場](../records/exec-as-pure-cpu.md) 提到 git 自己走過這條路又走回來——`git-commit.sh` 當年真的去 fork `git-update-index`，後來一支支收回成 C builtin，理由之一是**錯誤穿不過退出碼**。
