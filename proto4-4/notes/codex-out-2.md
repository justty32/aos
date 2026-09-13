完成；只修改 `proto4-4/`，沒有 commit、push 或開 agent。
改了 `README.md`、`src/aos.janet`、`src/step.janet`、三支測試及 `test/fx/` fixtures。
`test/aos.janet`：34 條；最後一行原文：`34 條通過 ✓`
`test/step.janet`：26 條；最後一行原文：`26 條通過 ✓`
`test/cpu.janet`：4 條；最後一行原文：`4 條通過 ✓`
自行決定：沒 capture/read 時不放 `:out`；取值仍是 nil。
自行決定：`pipe` 複製最後結果再加 `:steps`，避免產生循環 table。
撞到的坑：spork JSON cfunction 不能直接存進 image，改為解碼當下動態載入；跨進程實測已過。
沒做到的：無；README 145 行，`git diff --check` 也通過。