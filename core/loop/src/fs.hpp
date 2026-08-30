#pragma once

#include <aos/export.h>

#include <csignal>
#include <string>
#include <vector>

#include <sys/types.h>

namespace aos::loop::fs {

bool read_file(const std::string &path, std::string &text,
               std::string &error);
bool write_atomic(const std::string &path, const std::string &text,
                  std::string &error);
bool mkdir_p(const std::string &path, std::string &error);
std::vector<std::string> list_json_files(const std::string &dir,
                                         std::string &error);
std::string realpath_of(const std::string &path);
std::string join(const std::string &left, const std::string &right);
std::string basename_sans_json(const std::string &path);

}  // namespace aos::loop::fs

namespace aos::loop::detail {

struct DaemonProcess {
    pid_t pid = -1;
    int notify_fd = -1;
    bool child = false;
};

/* run 的訊號 handler 把它設成 1，wait_for_delivery 看到就立刻回來——
 * 不然 aos stop 得等滿一個 interval 才收得到。只准在 handler 裡指派。 */
AOS_API extern volatile sig_atomic_t stop_requested;

DaemonProcess daemonize(const std::string &log_path, std::string &error);
bool await_daemon(const DaemonProcess &process, std::string &error);
void notify_daemon(int fd, bool ready);

}  // namespace aos::loop::detail
