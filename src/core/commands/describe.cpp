#include "commands.hpp"

#include <cstddef>
#include <format>
#include <ranges>
#include <string>

namespace aos::builtin {

// 沒對上任何命令時的後備。把 CLI 送過來的東西原樣列出來，
// 用來確認參數邊界（空字串、引號、非 ASCII）在傳輸過程中沒有被動過。
asio::awaitable<std::int32_t> describe(CommandContext& context) {
    const auto& arguments = context.request.arguments;

    auto report = std::format("daemon 收到 {} 個參數\n", arguments.size());
    for (const auto [index, argument] : std::views::enumerate(arguments)) {
        report += std::format("argv[{}] = <{}>\n", index, argument);
    }
    report += std::format("工作目錄 = {}\n",
                          context.request.working_directory.native());

    // stdin 不再整份留在記憶體裡，所以這裡只累計長度。
    std::size_t input_size = 0;
    while (true) {
        const auto chunk = co_await context.session.read_input();
        if (chunk.empty()) {
            break;
        }
        input_size += chunk.size();
    }
    report += std::format("stdin = {} bytes\n", input_size);

    co_await say(context.session, std::move(report));
    co_return 0;
}

}  // namespace aos::builtin
