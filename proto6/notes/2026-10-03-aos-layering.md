# aos 的分層：運行層、時空、kernel、agent（使用者想法，2026-10-03）

← [筆記索引](README.md)

**這是使用者口述的想法，照原意整理，不是裁定。** 當天的脈絡是在討論 daemon 減法、改成 FUSE，以及 tick 要不要改成 thread 和 lib，見 [thread 與程序評估](proposals/2026-10-03-thread-vs-process/README.md)。

## 四層，由下往上

1. **daemon 是運行層。** 它是 aos 體系和 Linux 系統之間的介面。在 daemon 之上，可以完全脫離 Linux，做 aos 自己的抽象世界。
2. **aos 的時空：檔案系統是空間，tick 是時間。**
   - tick 本質上是一個動作，每次動作後會進行一些行為。
   - aos 體系依託 tick 做時間上的判斷。
   - **tick 是程式還是 lib 都可以，形式無所謂。** 採用 inst JSON 當基底，只是因為它在 Linux 上最通用。
3. **kernel 運行在 aos 時空之上**，也就是檔案系統加 tick。排程和資源管理都依託在這上面。
4. **最後才是 agent。**

```mermaid
flowchart BT
  L["Linux"] --> D["daemon：運行層，aos 與 Linux 的介面"]
  D --> ST["aos 時空：檔案系統＝空間、tick＝時間"]
  ST --> K["kernel：排程與資源管理"]
  K --> A["agent"]
```

## 往下延伸（使用者，同日稍後）

- **tick 是動作，也能在一定程度上當時間單位。** 它是 aos 體系下唯一必有的時間單位：tick 動作啟動後，這個回合就開始了。
- **tick-tock（還在想，只是一個方法）。** tick 動作結束代表回合開始，tock 動作結束代表回合結束。
- **空間邊界＝daemon 能訪問的資料夾。** 因為 aos 運行在 daemon 上，daemon 提供、我們能訪問的資料夾就是空間的邊界。
- **「脫離 Linux」是口號。** 實際上是提供一個脫離 Linux 的接口，硬要接回 Linux 也可以。所謂脫離，就是像現在這樣：所有動作都基於 inst，inst 由 tick 和 daemon 安排。
- **kernel 的資源可以無限定義。**

## 跟同日討論的關係

以下是 Claude 對照同一天的討論列出的，不是使用者的原話：

- daemon 減法把 cgroup、切帳號、權限從 daemon 拉出來。這些是 Linux 那一側的事，運行層只負責把 aos 時空撐起來。
- 「tick 形式無所謂」表示「tick 是程序還是 lib」屬於運行層的實作選擇，不是 aos 時空的定義。
- 10-02 的 [kernel 提案](proposals/2026-10-02-kernel/README.md)和 [agent 提案](proposals/2026-10-02-agent/README.md)正好對到第 3、4 層。
