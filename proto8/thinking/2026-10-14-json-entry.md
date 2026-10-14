# 2026-10-14 函數的統一入口改成 JSON

← [討論紀錄](README.md)｜前一份：[kernel／agent](2026-10-13-kernel-agent.md)

> 10-14 中午（公司 WSL），使用者吃飯時的想法，打字。

## 0. 背景

今天上午只做規劃：aos-llm／aos-agent 規劃與 ctl／state、inst↔LLM 工具轉接兩份研究（皆 AI 建議、未拍板；網頁 https://claude.ai/artifact/K2aQ7KCad1u3dFTfDvArda 、https://claude.ai/artifact/HvrESfVs7MAM7t6hXBFFYu ）。使用者今天說：tasks 與 tick 忽略；公司這台不用 146、今天不實打 LLM；ctl／state 最好都統一規範。

## 1. 使用者原文（照原意整理）

原話：「posix呼叫格式，還有lisp的那套list呼叫方式，我覺得最大的痛點就是和json脫節。posix呼叫，表述的是一個函數的統一入口，lisp也是，兩者也不通，我在想，要是能讓函數的統一入口，變成參數統一成json就好了，這樣可以直接對接llm工具，乃至於python等腳本語言，而且和檔案系統也能很好的合作。我知道當年因為資源不足，所以不能用map，只能用list或array，但現在有了，所以...。」

要點：
- POSIX 的呼叫格式、LISP 的 list 呼叫方式，最大的痛點是和 json 脫節。
- POSIX 呼叫表述的是一個函數的統一入口，LISP 也是；兩者彼此也不相通。
- 想法：讓函數的統一入口，參數統一成 json。
- 好處：可以直接對接 llm 工具，乃至 python 等腳本語言，而且和檔案系統也能很好地合作。
- 當年資源不足，所以不能用 map，只能用 list 或 array；現在有了，所以...（話沒說完）

## 2. 未決

- 還沒討論，等使用者繼續說。
