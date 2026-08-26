# workflows on aos — 還在生長的想法與明顯的坑

← [本場索引](README.md)｜[workshop](../../README.md)

沒有收攏的五條想法（活狀態能不能跨機、何時升 world／lane、人能不能直接改 machine state、module 的責任、`doctor`），以及四位點名不能踩的坑。

---

## 還在生長的想法

### 活狀態要可 Git、可跨機，還是純本機執行狀態

這是最關鍵也最沒有答案的一條。三位的 `.aos/wf/*.json` 很適合 rename 與 generated status；研究
人員的 `wf/open/*.md` 很適合 Git、跨機與人直接改。四位都明說：若 open 狀態要進 Git，`.aos`
不能是唯一真源。也可能反過來決定 open 只屬當前機器，跨機靠 export／sync，但沒人提出完成形狀。

### task 何時才值得升成 world／lane

四位都先保留「短流程只是 task」。分界的說法略不同：獨立等待、反覆收件、跨回合恢復、需要
自己的 queue 時，才可能升 world／lane。工程師甚至提醒 workshop 不該只因等待就自動成 lane；
這表示升格不能只看時間長，而要看是否真的需要獨立執行與收件。

### 人能不能直接改 machine state

工程師說人可以改 `ready/<id>.json`，下一次 tick 採用；架構師、開發者則傾向由命令更新、markdown
只作 generated view；研究人員直接把真源放 markdown。三種都保留了「人可修」，但修的是 JSON、
命令還是 front matter 尚未收攏。

### non-invasive import 可以長成 module，但名字與責任未定

install／init／module add 三種名字背後是同一個想法：文件仍放 `wf/`，不把專案原目錄弄亂；機器
狀態放 `.aos/wf` 或另一個明示位置；upstream metadata 記模板來源。還未回答的是 module 只管理
安裝／升級，還是也負責 task runtime。

### `doctor` 可能比自動 upgrade 更安全

只有工程師提出 `doctor`：先找 placeholder、壞連結與孤兒路由，不替人合併政策。這條沒有多人
呼應，但與四位「upgrade 只顯示三方差異、不蓋客製」的邊界相容，所以讓它單獨留著。

## 明顯的坑

- **把推論寫成使用者痛點。**四位只從檔案看到 drift 與手工步驟；使用者尚未說自己最痛的是哪個。
  若先做 install、router 或 task DB，可能精準消滅一個他根本不在乎的步驟。

- **把所有 markdown 編成 JSON**。**四位獨立地都反對**：意圖、理由、例外與 gotchas 需要模型
  理解和人審；結構化副本只會和原文漂移。

- **同時手改 SESSION-LOG／WAIT_USER，又讓 `.aos` 當真源。**status 若是 generated view，就不能
  再接受另一條手工維護鏈；若 markdown 要可編輯，它就必須有明確反寫／reconcile 規則。

- **把 inbox 直接接到 `inst.tempd`**。**四位獨立地都分開兩者**：信可以不回，instruction 必須
  claim。缺少 `accept` 這道明示升格，知會信會變成強制工作。

- **活狀態放進通常不版控的 `.aos`，卻期待它自然隨 Git 跨機**。**四位都標記這是未知前提**；
  真源位置不拍板，任何 layout 都可能在第一天就放錯層。

- **upgrade 自動覆蓋客製 workflow**。**四位都只接受來源版本＋三方 diff**；開發者更明說只替換
  未修改檔。模板是基底，不是活實例的遠端真源。

- **把每個 workflow 都升成 lane。**四位都先保留 task；若只是「步驟多」或「等過人」，不代表
  它需要獨立 queue、kernel 與生命週期。

- **tick 先改 cursor，再 Deliver。**工程師明確要求成功投遞後才前進；順序反了，task 會被標成
  已喚醒，但 queue 裡沒有下一步。
