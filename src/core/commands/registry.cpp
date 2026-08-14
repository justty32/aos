// 命令註冊表 —— 要新增命令，改下面那兩張表就好。
#include "commands.hpp"

#include <algorithm>
#include <array>
#include <format>
#include <ranges>
#include <string>

namespace aos {
namespace {

// 子命令的表。巢狀就是這樣長出來的：一個分組節點指向自己的子表。
[[nodiscard]] std::span<const Command> daemon_children() {
    static const std::array table{
        Command{"status", "顯示已經活多久、服務過幾次", builtin::daemon_status},
        Command{"stop", "請 daemon 做完手上的事之後收工", builtin::daemon_stop},
    };
    return table;
}

[[nodiscard]] std::span<const Command> llm_children() {
    static const std::array table{
        Command{"ask", "問一句話，會自己跑工具（串流輸出）", builtin::llm_ask},
        Command{"models", "端點上有哪些模型", builtin::llm_models},
        Command{"tools", "AOS_LLM_TOOLS 載得到哪些工具", builtin::llm_tools},
    };
    return table;
}

[[nodiscard]] const Command* find_child(std::span<const Command> level,
                                        std::string_view name) {
    const auto match = std::ranges::find(level, name, &Command::name);
    return match == level.end() ? nullptr : &*match;
}

}  // namespace

std::span<const Command> commands() {
    // function-local static：第一次呼叫時才建，之後都是同一份。
    static const std::array table{
        Command{"ping", "回覆 pong，用來確認 daemon 還活著", builtin::ping},
        Command{"echo", "把 stdin 原封不動送回 stdout（串流）", builtin::echo},
        Command{"help", "列出所有命令", builtin::help},
        // 分組節點：沒有 run，只有 children。
        Command{"daemon", "操作常駐程式本身", nullptr, daemon_children()},
        Command{"llm", "呼叫語言模型", nullptr, llm_children()},
    };
    return table;
}

Resolution resolve_command(std::span<const std::string> arguments) {
    std::span<const Command> level = commands();
    Resolution result;

    for (const std::string& token : arguments) {
        const Command* match = find_child(level, token);
        if (match == nullptr) {
            break;
        }
        result = {.command = match, .depth = result.depth + 1};
        level = match->children;
        if (level.empty()) {
            break;  // 葉節點，後面的都是它的參數
        }
    }
    return result;
}

std::span<const std::string> CommandContext::path() const {
    return std::span{request.arguments}.first(depth);
}

std::span<const std::string> CommandContext::operands() const {
    return std::span{request.arguments}.subspan(depth);
}

std::string render_command_list(std::span<const std::string> path,
                                std::span<const Command> level) {
    const auto prefix =
        path.empty() ? std::string{"aos"}
                     : std::format("aos {}", path | std::views::join_with(' ') |
                                                 std::ranges::to<std::string>());

    // 對齊名稱欄，讓輸出好讀。
    const auto widest = std::ranges::max(
        level | std::views::transform(
                    [](const Command& command) { return command.name.size(); }));

    auto text = std::format("用法：{} <command> [arguments...]\n\n可用的命令：\n",
                            prefix);
    for (const Command& command : level) {
        // 分組節點標一下，使用者才知道後面還有一層。
        const auto marker = command.is_group() ? " …" : "";
        text += std::format("  {:<{}}  {}{}\n", command.name, widest,
                            command.summary, marker);
    }
    return text;
}

asio::awaitable<std::int32_t> handle_command(const Request& request,
                                             Session& session,
                                             Runtime& runtime) {
    runtime.count_request();

    const auto [command, depth] = resolve_command(request.arguments);
    CommandContext context{.request = request,
                           .session = session,
                           .runtime = runtime,
                           .depth = depth};

    if (command == nullptr) {
        // 完全沒給命令 → 列出有什麼可用；給了但認不得 → 印出收到的內容除錯。
        if (request.arguments.empty()) {
            co_await complain(session, render_command_list({}, commands()));
            co_return 2;
        }
        co_return co_await builtin::describe(context);
    }

    // 走到分組節點卻沒再往下（例如只打 `aos daemon`）：列出它的子命令。
    if (command->run == nullptr) {
        co_await complain(session,
                          render_command_list(context.path(), command->children));
        co_return 2;
    }

    co_return co_await command->run(context);
}

}  // namespace aos
