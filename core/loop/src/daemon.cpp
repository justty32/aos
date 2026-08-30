#include "fs.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>

#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aos::loop::detail {

DaemonProcess daemonize(const std::string &log_path, std::string &error) {
    const char *const log_path_data = log_path.c_str();
    int ready_pipe[2] = {-1, -1};
    if (::pipe(ready_pipe) != 0) {
        error = std::string("無法建立 daemon 通知管線: ") +
                std::strerror(errno);
        return {};
    }

    std::fflush(nullptr);
    const pid_t pid = ::fork();
    if (pid < 0) {
        const int saved_errno = errno;
        ::close(ready_pipe[0]);
        ::close(ready_pipe[1]);
        error = std::string("無法 fork 背景 loop: ") +
                std::strerror(saved_errno);
        return {};
    }
    if (pid > 0) {
        ::close(ready_pipe[1]);
        return {.pid = pid, .notify_fd = ready_pipe[0], .child = false};
    }

    ::close(ready_pipe[0]);
    if (::setsid() < 0) {
        const char failed = '0';
        ::write(ready_pipe[1], &failed, 1);
        ::close(ready_pipe[1]);
        ::_exit(1);
    }
    const int log_fd = ::open(log_path_data, O_WRONLY | O_CREAT | O_APPEND,
                              0644);
    if (log_fd < 0 || ::dup2(log_fd, STDOUT_FILENO) < 0 ||
        ::dup2(log_fd, STDERR_FILENO) < 0) {
        const char failed = '0';
        ::write(ready_pipe[1], &failed, 1);
        if (log_fd >= 0) ::close(log_fd);
        ::close(ready_pipe[1]);
        ::_exit(1);
    }
    if (log_fd != STDOUT_FILENO && log_fd != STDERR_FILENO) ::close(log_fd);
    return {.pid = 0, .notify_fd = ready_pipe[1], .child = true};
}

bool await_daemon(const DaemonProcess &process, std::string &error) {
    char ready = '0';
    const ssize_t count = ::read(process.notify_fd, &ready, 1);
    ::close(process.notify_fd);
    if (count == 1 && ready == '1') return true;

    int status = 0;
    while (::waitpid(process.pid, &status, 0) < 0 && errno == EINTR) {
    }
    error = "背景 loop 啟動失敗";
    return false;
}

void notify_daemon(int fd, bool ready) {
    if (fd < 0) return;
    const char value = ready ? '1' : '0';
    ::write(fd, &value, 1);
    ::close(fd);
}

}  // namespace aos::loop::detail
