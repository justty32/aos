#pragma once

// `_type: "exec"` —— 跑一個 Linux 執行檔：argv + stdin/stdout/stderr + exit status。
// 跟 aos 自己的命令是同一組三件套，這不是巧合：那本來就是 Linux 上「一次執行」的
// 全部內容。
//
// `_extra` 長這樣：
//
//   {
//     "_version": "0.1.0",
//     "_type": "exec",
//     "exec": ["./resize"],                       // 第一項是程式本身
//     "argv": {                                   // 參數怎麼變成命令列
//       "path":  {"position": 1},                 // 位置參數
//       "width": {"position": 2, "flag": "-w"},   // 旗標加值
//       "force": {"flag": "--force"}              // boolean → 開關
//     },
//     "stdin":  {"param": "text"},                // 這個參數改走 stdin
//     "stdout": {"clip": "head"},                 // 太長要截頭還是截尾
//     "stderr": {"mode": "merge"},                // merge / ignore / only
//     "ok_exit": [0, 1]                           // 這些結束碼不算失敗
//   }
//
// **沒有 kind 這種欄位**，命令列上長什麼樣是推導出來的：沒 flag 就是位置參數；
// 有 flag 又是 boolean 就是開關（真值才放旗標）；其餘是旗標加值。
// schema 的型別是唯一真相，同一件事不講第二遍。
//
// **不經過 shell。**argv 是一個陣列，直接 execvp，所以模型給的參數值裡有
// `;`、`$(...)`、空白都只是字元，不會被重新解析。這是相對於「叫模型自己寫 shell
// 指令」的實質差別，不只是省 token。

#include "aos/tooljson/spec.hpp"

#include <expected>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tooljson {

// 一次執行的配方：要跑什麼、餵什麼進 stdin。
struct ExecPlan {
    std::vector<std::string> argv;

    // 沒有宣告 stdin，或模型沒給那個參數，就是 nullopt（子行程讀到 EOF）。
    std::optional<std::string> stdin_text;
};

// 模型給的那包 JSON → 一次執行的配方。純函式，不碰 process，所以測得起來。
//
// 錯誤是**要交回給模型的那句話**（「少了必填參數 path」），不是給人看的。
[[nodiscard]] std::expected<ExecPlan, std::string> plan_exec(
    const Spec& spec, std::string_view arguments_json);

// 一次 tool 回傳最多塞給模型幾個字元。超過就截，並註明省略了多少。
inline constexpr std::size_t max_output_characters = 30000;

// 子行程的輸出 → 給模型看的字串。含 NUL 就當二進位，
// 不吐一堆替代字元灌爆 context。
[[nodiscard]] std::string decode_output(std::string_view raw);

// 太長就截。編譯器那種重點在尾巴的用 "tail"。
[[nodiscard]] std::string clip_output(std::string text,
                                      std::string_view where = "head",
                                      std::size_t limit = max_output_characters);

// 跑任意執行檔，危險程度跟給模型一個 shell 同級，所以留一個守門員。
// 預設全放行；回 false 就不執行，改回一句話給模型。
using Approver = std::function<bool(const std::string& tool_name,
                                    const std::vector<std::string>& argv)>;
void set_approver(Approver approver);

}  // namespace aos::tooljson
