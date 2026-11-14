常見問題先看結論：aos 是原型，目前能不用模型跑起一棵樹；多機連線與安全隔離都還沒有。

# 常見問題

<!-- source: 06-草稿/文案表.json P1,FULL,S1,SEC; 08-批0實測.md; 03-計劃.md 第 2 節 -->

**aos 是什麼？**

<!-- copy:P1 -->
aos 把 AI agent 當成一般的 Linux 行程，住在資料夾裡。每個工具、每隻 agent、每封信，都是你可以 ls、可以讀、可以設權限的資料夾或檔案。
名字：<!-- copy:FULL -->aos：akatosh operating system。

**需要模型帳號嗎？**
不用。L0 用假腦，只要 Linux、git、Python 3.11 以上、CMake、C++ 編譯器與 nlohmann-json。要換真腦才需要 OpenAI 相容端點與金鑰。見[安裝總覽](install/index.md)。

**要裝 Python 套件嗎？**
不用。Python 這一側零第三方套件，沒有 pip、沒有 venv。

**支援 Windows 或 macOS 嗎？**
<!-- copy:S1 -->
只支援 Linux（WSL2 可以；WSL2 本稿未實跑）。Windows、macOS 原生版本目前沒有。

**安全嗎？**
<!-- copy:SEC -->
agent 會用你的帳號執行程式，同帳號沒有隔離。請在拋棄式帳號、容器，或丟了也不心疼的資料夾裡試；沙箱是實驗功能。見[安全說明](manual/security.md)。

**可以兩台機器同時跑同一棵樹嗎？**
不行。一棵樹一次住一台；可以把整棵樹搬到另一台接著跑（輪流跑）。樹與樹之間沒有內建連線。

**檔案格式會變嗎？**
會。這是原型，檔案格式和指令還會變，也沒有舊版相容。

**出錯了怎麼辦？**
先看[疑難排解](manual/troubleshooting.md)，第一條是停樹與清殘留。
