← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**kernel**｜概念：本檔｜規範：[N-42](../NORMS/09-kernel.md)（兩種 kernel，草稿；打包 N-03 在 [NORMS 時空](../NORMS/02-設計理念-時空.md)；kernel 公告、`_metainfo` 在 [NORMS 待定](../NORMS/08-待定.md)）｜實作：LLM kernel 是 [aos-llm-kernel](../../impls/aos-llm-kernel/README.md)＋寄信收信的基礎工具 [aos-llm](../../impls/aos-llm/README.md)（11-04 晚由 aos-llm-send 改名；信帶請求、kernel 用 aos-exec 跑自己的 endpoint 函數〔11-05 改：kernel 不自己跑、請 daemon 掛問腦 proc，N-42 (1)〕）＋範本 [kernel/llm-kernel](../../kernel/docs/01-llm-kernel.md)（[thinking 2026-10-24-llm-kernel](../../thinking/2026-10/24/llm-kernel/README.md)、[11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)），通用 kernel 現無實作；討論見 [thinking 10-13 kernel／agent](../../thinking/2026-10/13/kernel-agent/README.md)）

# kernel

- **C-09** 任務處理過程中用到的東西，只要有限，就是資源。（2.7）
- **C-10** 資源的有限用格數表示。（3b）
- **C-11** 排序演算法＝決定哪個任務先給哪個資源；就這樣，不多說。（2.7）
- **C-12** 排序與資源分配本身是計算任務；資源本身也當行程看——一切都是計算任務，核心沒有第二種東西。（2.8）〔這裡的「核心」＝名詞表的「系統本體」，不是 C-74 分層裡的核心 aos-exec〕
- **C-13** 每個計算任務都有固定的基礎特性（九軸）；其中確定性是任務自己的屬性。（2.9）
- **C-14** 基礎特性之外，人可以任意附加特性。（2.9）
- **C-15** 排序程式可以由人寫，也可以由「生成排序程式的程式」叫模型寫。（2.10）
- **C-28** 沒法直接轉成 POSIX 呼叫的事（人手畫），用**間接抽象化**變成計算任務：拆成多個 POSIX 任務（寄信給畫家、收信、畫歸檔），人在這幾個任務之間、在系統外面做事。（3c）
- **C-29** 處理單元分兩種：普通 CPU（跑寄信、收信這類一般任務）；外部 PU（畫師、GPU、NPU）——跟外部設備的概念靠攏。（3d）
- **C-38** 第三層（kernel）的參照物就是時間（tick-tock）與空間（資料夾）：「三回合內搞定」「只動這三個資料夾」「每檔不超過幾 KB」。它只是一個排程；PU 怎麼收任務請求各資料夾各做各的。（3g.6）
- **C-47** kernel 的定義分兩層（10-15 使用者定）。**原生定義**（寬泛）：能夠管理哪些東西被執行或被使用的一個東西。**aos 實作定義**（為了實作補充）：在當前 aos 計劃下，kernel 就是以 inst／loop／daemon 為基礎，能夠管理某一 inst 是否被執行的，一個正在執行、或是被執行的 inst。相關：資源與排序 C-09～C-15、處理單元 C-29、參照物 C-38、間接抽象化 C-28；kernel 初步分兩種見 [N-42](../NORMS/09-kernel.md)。
  - **11-05 加嚴**（使用者 11-05「kernel的定義是管理某proc是否可以執行」「他的proc是掛在linux底下，而非daemon底下。不太...好」「假如他判斷要跑這個請求的時候，所做的動作是把請求轉交給另一個真正有權限的kernel，那他也算kernel嗎？我覺得是算的，他的命名中也可以帶有kernel，只是說，建議不要濫用...。除此之外，假如他判斷要跑這個請求後，所做的動作是直接執行linux原生proc，或是一些函數，那他算kernel嗎？我覺得是不算的...」；衝突 1 使用者選「加嚴」、後裁蓋前裁，[thinking 11-05 kernel-daemon 05](../../thinking/2026-11/05/kernel-daemon/05-衝突與方向題.md)）：aos 實作定義收緊——**被管的 proc 要掛在 daemon 下**；判斷後**自己 fork 跑 Linux 原生程序或函數的不算** kernel；判斷後**轉交給有權的 kernel 的算**（命名可以帶 kernel、別濫用）。daemon 自己是最基礎的 kernel（來者不拒，[附錄1](附錄1-名詞.md) daemon 列）。掛 proc 只有一條路：往 daemon 的 ctl 信箱寄 `procs_*` 信；兩種模式——**繼承式**（daemon.json 的 `exec` 身體當判官、判完轉寄進自己的 ctl 信箱＝「呼叫 base」）、**0 號 proc 式**（唯一能對 daemon 下 ctl 的 kernel proc，其他人把請求丟給它），見 [kernel-daemon 02](../../thinking/2026-11/05/kernel-daemon/02-兩種模式.md)。0 號式的「唯一」**靠 Linux 權限＋約定、程式不驗身分**（衝突 2 使用者選「Linux 權限＋約定」並補：「linux權限沒設也可以(因為我知道有些人嫌麻煩，或是還處在demo狀態)，就自行承擔風險。」——帳號／權限沒分開時「唯一」只是約定，繞過＝使用者自擔，不當錯誤處理）。
  - **11-06 註**（說明，不是新規則；[os-concepts 02 § 疑似衝突的建議](../../thinking/2026-11/06/os-concepts/02-OS與kernel-能借鑒.md#跟既有原則已裁的關係)）：C-11／C-12「排序＝kernel 的事」跟 C-47 加嚴「kernel＝管掛不掛」是原生定義（寬）與實作定義（窄）兩層，不衝突——排序由 kernel 的身體做，掛不掛由 daemon 做。
