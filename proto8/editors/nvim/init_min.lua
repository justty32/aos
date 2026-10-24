-- init_min.lua - 不碰你的 LazyVim 設定，單獨試 aos_nvim：
--   nvim --clean -u ~/repo/simple_tools/aos/proto8/editors/nvim/init_min.lua
-- 工作區＝環境變數 AOS_WS，沒設＝nvim 的 cwd（進去後 :AosWs 資料夾 可以改）。
local here = debug.getinfo(1, "S").source:sub(2):match("^(.*)/init_min%.lua$")
vim.opt.rtp:prepend(here)
vim.g.mapleader = " "
vim.g.maplocalleader = ","
require("aos_nvim").setup({ ws = vim.env.AOS_WS })

-- 試用的鍵（你自己的設定裡要不要、綁哪個鍵自己定）
local aos = require("aos_nvim")
vim.keymap.set("n", "<localleader>ax", "<cmd>AosExec<cr>", { desc = "aos：跑目前的 aos 程式" })
vim.keymap.set("n", "<localleader>a1", "<cmd>AosExec!<cr>", { desc = "aos：跑目前這個檔（fsm 走一格）" })
vim.keymap.set("n", "<localleader>at", "<cmd>AosTrace<cr>", { desc = "aos：看 trace" })
vim.keymap.set("n", "<localleader>ag", function() aos.jump() end, { desc = "aos：跳到游標下的 檔#/指標" })
vim.keymap.set("n", "<localleader>ap", "<cmd>AosLuaPreview<cr>", { desc = "aos：預覽 Lua 編出的 JSON" })
vim.keymap.set("n", "<localleader>ab", "<cmd>AosLuaBuild<cr>", { desc = "aos：Lua 編成資料夾" })
