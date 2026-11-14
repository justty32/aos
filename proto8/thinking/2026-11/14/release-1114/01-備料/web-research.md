# 同類開源專案 README／文件站調查（sonnet，11-14，curl 抓公開頁）

## 各專案
- AutoGen：logo＋5 badge、一句話、pip 一行、Quickstart 片段；已封存（CAUTION 置頂）。文件 Sphinx（pydata theme）。
- CrewAI：logo＋導覽列＋badge；README 741 行太長。文件 Mintlify、多語言分組。
- LangGraph：極短 README（82 行），一行 pip、特色清單各連文件。文件 Mintlify＋llms.txt。
- OpenHands：截圖、Quickstart 分四級（無沙箱→Docker→多 Docker→原始碼）。文件 Mintlify。←安裝分級最值得學
- Letta：README 38 行、一行安裝一行啟動。文件 Astro Starlight。
- smolagents：特色 4 條、「How smol」用行數講規模、Security 獨立一節；文件 HF doc-builder，頂層 Get started／Tutorials／Conceptual guides／Examples／Reference，含 zh。
- Aider：終端機錄影 SVG、好評牆；文件 Jekyll just-the-docs 跑在 GitHub Pages。
- goose：README 63 行，curl|bash 一鍵腳本指向 Releases 預編檔、桌面版。文件 Docusaurus。
- AIOS（最像我們）：架構圖置前（kernel、SDK）、5 種部署模式（本機／遠端 kernel）、git clone＋venv。README 459 行過長。文件 GitBook。

## 綜合
- README 骨架：logo、標語、4～6 badge、一句話、截圖/GIF、安裝 1～3 行、Quickstart、特色、架構/文件連結、社群、授權。趨勢是短 README、細節進文件站。
- 文件目錄：Get started／Tutorials(Guides)／Concepts(Architecture)／Examples／Reference／Changelog。
- 降門檻：預編二進位＋一行腳本（goose）、安裝分級（OpenHands）、Docker。devcontainer 未查到。
- 產生器：
  - MkDocs Material：Actions `mkdocs gh-deploy`→gh-pages；多語言要每語言一子專案（mkdocs-static-i18n 已凍結；官方提到轉向 Zensical）。
  - VitePress：Actions upload-pages-artifact＋deploy-pages、`base:'/repo/'`；內建 locales（docs/zh/）；要 Node。
  - Jekyll：Pages 原生，可直接從 `/docs` 夾，不用 workflow；外掛受白名單限，多語言自理。
  - Docusaurus 官方 i18n 最完整；Starlight 有 i18n。
- 未查到：devcontainer 使用、Jekyll 官方多語言、首頁實際區塊順序（只讀 README 與導覽設定）。

## 來源
raw.githubusercontent.com/<org>/<repo>/main/README.md（microsoft/autogen、crewAIInc/crewAI、langchain-ai/langgraph、All-Hands-AI/OpenHands、letta-ai/letta、huggingface/smolagents、Aider-AI/aider、block/goose、agiresearch/AIOS）；mkdocs-material publishing-your-site.md、changing-the-language.md；vitepress deploy.md、i18n.md；jekyll github-pages.md；docusaurus i18n-introduction.mdx；starlight i18n.mdx；sphinx intl.rst；github/docs configuring-a-publishing-source。
