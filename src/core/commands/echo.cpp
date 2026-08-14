#include "commands.hpp"

#include <string>

namespace aos::builtin {

// 邊讀邊寫，任何時刻只有一塊資料在記憶體裡。
// 這是驗證串流是否真的有效的最小命令：`tail -f x | aos echo` 應該即時有輸出，
// 而且 `cat 大檔 | aos echo` 不會因為超過訊框上限而失敗。
asio::awaitable<std::int32_t> echo(CommandContext& context) {
    while (true) {
        // chunk 是這個 coroutine frame 的區域變數，撐得過下面的 co_await。
        const auto chunk = co_await context.session.read_input();
        if (chunk.empty()) {
            co_return 0;
        }
        co_await context.session.write_output(chunk);
    }
}

}  // namespace aos::builtin
