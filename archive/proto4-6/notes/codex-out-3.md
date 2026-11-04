完成，只修改 `proto4-6/`，沒有 commit、push 或連網。  
新增：`aos-step-lua` 222 行；`lua/json.lua` 178 行；`lua/base64.lua` 41 行；`lua/aos.lua` 143 行。  
測試：`test/test_step_lua.py` 210 行、22 條 Lua 測試；README 150 行。  
`proto4-6` 全套共 52 tests，最後一行：`OK`。  
repo 根目錄 build 成功，ctest 8/8 全綠。  
自行定案：`src` 保存 `size`、`mtime`、步驟名字；空 Lua table 一律視為 `{}`。  
坑：Lua 空陣列和空物件無法區分；依定案選擇空物件。沒漏做已知項目。