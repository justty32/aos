#include <aos/tick.hpp>

#include <cerrno>
#include <cstring>
#include <exception>
#include <filesystem>

#include <fcntl.h>
#include <unistd.h>

namespace aos::tick {

std::string format_log_line(Instant now, const std::string &tz,
                            std::uint64_t turn,
                            const std::vector<Event> &events) {
    if (events.empty()) return {};

    std::string line = format_timestamp(now, tz) + " turn=" +
                       std::to_string(turn);
    for (const auto &event : events) {
        std::string target = event.target;
        for (char &ch : target) {
            if (ch == '\n' || ch == '\r') ch = ' ';
        }
        line += " " + event.kind + "=" + event.id + "→" + target;
    }
    line += '\n';
    return line;
}

bool append_log(const std::string &path, const std::string &line,
                std::string &error) {
    error.clear();
    if (line.empty()) return true;

    try {
        const std::filesystem::path parent =
            std::filesystem::path(path).parent_path();
        if (!parent.empty()) std::filesystem::create_directories(parent);
    } catch (const std::exception &exception) {
        error = "無法建立 log 父目錄: " + std::string(exception.what());
        return false;
    }

    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) {
        error = "無法開啟 log: " + std::string(std::strerror(errno));
        return false;
    }

    const ssize_t written = ::write(fd, line.data(), line.size());
    const int write_errno = errno;
    const int close_result = ::close(fd);
    if (written < 0 || static_cast<std::size_t>(written) != line.size()) {
        error = written < 0 ? "無法寫入 log: " +
                                  std::string(std::strerror(write_errno))
                            : "無法一次寫完整行到 log";
        return false;
    }
    if (close_result != 0) {
        error = "無法關閉 log: " + std::string(std::strerror(errno));
        return false;
    }
    return true;
}

}  // namespace aos::tick
