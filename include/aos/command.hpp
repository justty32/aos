#pragma once

#include "aos/protocol.hpp"
#include "aos/runtime.hpp"
#include "aos/session.hpp"

#include <asio/awaitable.hpp>

#include <cstddef>
#include <cstdint>
#include <functional>
#include <span>
#include <string>
#include <string_view>

namespace aos {

// 一個命令看得到的世界，就是三件套：
//   1. 三條標準串流  → context.session（read_input／write_output／write_error）
//   2. 參數          → context.operands()
//   3. exit status   → 函式的回傳值
// 其他都是額外奉送的。要多給命令什麼，加欄位在這裡就好，
// 不必去改每個命令的簽名。
struct CommandContext {
    const Request& request;  // 完整的 arguments 與 working_directory
    Session& session;        // stdin／stdout／stderr
    Runtime& runtime;        // 跨呼叫存活的 daemon 狀態

    // 命令路徑用掉了幾個 argument。`aos daemon status` 走到 status 時是 2。
    std::size_t depth = 0;

    // 走到這個命令的名稱序列，上例是 {"daemon", "status"}。
    [[nodiscard]] std::span<const std::string> path() const;

    // 命令路徑之後剩下的參數，也就是命令自己該解讀的那些。
    // `aos daemon status --json` 走到 status 時是 {"--json"}。
    [[nodiscard]] std::span<const std::string> operands() const;

    // 方便用的縮寫。
    [[nodiscard]] const std::filesystem::path& working_directory() const {
        return request.working_directory;
    }
};

// 一個命令就是這樣一個函式：拿 context，回傳 exit status。
using CommandHandler =
    std::function<asio::awaitable<std::int32_t>(CommandContext&)>;

struct Command {
    std::string_view name;
    std::string_view summary;  // help 會列出來

    // 純分組的節點（例如 `daemon`）可以留空，這時只會列出它的子命令。
    CommandHandler run = nullptr;

    // 子命令。空的就是葉節點。
    std::span<const Command> children = {};

    [[nodiscard]] bool is_group() const { return !children.empty(); }
};

// 命令樹的根。要新增命令，改 src/core/commands/registry.cpp 裡的表就好。
[[nodiscard]] std::span<const Command> commands();

// 沿著命令樹往下走的結果。
struct Resolution {
    const Command* command = nullptr;  // 沒對上任何名稱時是 nullptr
    std::size_t depth = 0;             // 命令路徑吃掉了幾個 argument
};

// 從根開始，一個一個 argument 往下比對，走到不能再走為止。
[[nodiscard]] Resolution resolve_command(std::span<const std::string> arguments);

// 所有業務命令都從這個入口進入；CLI 不應包含命令語意。
[[nodiscard]] asio::awaitable<std::int32_t>
handle_command(const Request& request, Session& session, Runtime& runtime);

// help 與「這是個分組」的提示共用同一份渲染。回傳字串而不是直接寫出去，
// 因為 `aos help` 屬於正常輸出（stdout），而「你沒給命令」是錯誤（stderr）。
[[nodiscard]] std::string render_command_list(std::span<const std::string> path,
                                              std::span<const Command> level);

}  // namespace aos
