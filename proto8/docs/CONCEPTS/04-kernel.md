← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**kernel**｜概念：本檔｜規範：[N-42](../NORMS/09-kernel.md)（兩種 kernel，草稿；打包 N-03 在 [NORMS 時空](../NORMS/02-設計理念-時空.md)；kernel 公告在 [NORMS 待定](../NORMS/08-待定.md)；節點的描述抽屜是 [N-69](../NORMS/10-基礎設施-定義與工作區/11-N-69.md)（[檔名見 NORMS 命名續](../NORMS/命名-續-概念搬來的檔名.md)）、成本與逾時 N-68）｜實作：LLM kernel 在 [`py/tools/aos/kernel_llm`](../../py/tools/aos/kernel_llm/README.md)（通用 kernel 框架＋問腦那一包）＋寄信收信的基礎工具 [aos-llm](../../cpp/aos-llm/README.md)（信帶請求；kernel 不自己跑 endpoint 函數，請 daemon 掛問腦 proc 去跑，N-42 (1)）＋範本 [kernel/llm-kernel](../../templates/kernels/docs/01-llm-kernel.md)（[thinking 2026-10-24-llm-kernel](../../thinking/2026-10/24/llm-kernel/README.md)、[11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)）；通用 kernel 的站（框架站）是 [py/tools/aos/kernel](../../py/tools/aos/kernel/README.md)＋範本 [kernel/daemon-kernel、procs-kernel](../../templates/kernels/docs/02-kernel-modes.md)；討論見 [thinking 10-13 kernel／agent](../../thinking/2026-10/13/kernel-agent/README.md)

# kernel

- **C-09** 任務處理過程中用到的東西，只要有限，就是資源。（2.7）
- **C-10** 資源的有限用格數表示。（3b）
- **C-11** 排序演算法＝決定哪個任務先給哪個資源；就這樣，不多說。（2.7）
- **C-12** 排序與資源分配本身是計算任務；資源本身也當行程看——一切都是計算任務，核心沒有第二種東西。（2.8）〔這裡的「核心」是 aos 作業系統核心（[名詞表](附錄1-名詞.md)「核心」列）；C-74 分層裡的「核心」指 aos-exec，同詞兩義（使用者 11-17 選項框「改回「核心」」；待裁網頁 條文-1a 選 B）〕
- **C-13** 每個計算任務都有固定的基礎特性（九軸）；其中確定性是任務自己的屬性。（2.9）
- **C-14** 基礎特性之外，人可以任意附加特性。（2.9）
- **C-15** 排序程式可以由人寫，也可以由「生成排序程式的程式」叫模型寫。（2.10）
- **C-28** 沒法直接轉成 POSIX 呼叫的事（人手畫），用**間接抽象化**變成計算任務：拆成多個 POSIX 任務，人在這幾個任務之間、在系統外面做事。（3c）
- **C-29** 處理單元分兩種：普通 CPU（跑一般任務）；外部 PU（畫師、GPU、NPU）——跟外部設備的概念靠攏。（3d）
- **C-38** 第三層（kernel）的參照物就是時間（時鐘）與空間（資料夾）：「三回合內搞定」「只動這三個資料夾」「每檔不超過幾 KB」。kernel 管什麼見 C-47（資源管理＋排程；使用者 11-17 選項框「C-47：資源管理＋排程」）；PU 怎麼收任務請求各資料夾各做各的。（3g.6）
<a id="c-47"></a>
- **C-47** kernel＝「資源管理＋排程」，是從外面看進去的身分：請求寄到哪，那裡對寄件人就是 kernel。全文在 [04-kernel/01-C-47](04-kernel/01-C-47.md)（原生定義、一律寄 `AOS_KERNEL`、多種 syscall、轉交與鏈）與 [02-續-C-47](04-kernel/02-續-C-47.md)（擺法、安全保底、已裁定與現況、嵌套、例子）。

例：
- C-28：人手畫＝寄信給畫家、收信、畫歸檔三個 POSIX 任務。
- C-29：普通 CPU 跑寄信、收信這類一般任務。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-C-47](04-kernel/01-C-47.md) | C-47 kernel 的定義：原生定義與 aos 的說法、一律寄 `AOS_KERNEL`、多種 syscall、轉交也算 |
| [02-續-C-47](04-kernel/02-續-C-47.md) | C-47（續）：擺法不限、安全的保底是 Linux 本身、已裁定（狀態位址、通用 kernel 框架）與現況、一切都可以嵌套、C-11／C-12 與本條、例子 |
