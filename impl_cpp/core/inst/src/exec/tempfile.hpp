// tempfile.hpp：mkstemp 暫存檔：建、寫滿、讀回後 unlink（搬自 archive/aos-v1/core/exec，行為不改）。
#pragma once

#include <cstddef>
#include <string>

namespace aos::exec::detail {

int make_temp(const std::string &prefix, std::string &path_out);
bool write_fully(int fd, const char *data, std::size_t size);
bool read_file_and_unlink(const std::string &path, std::string &text,
                          std::string &error);
bool unlink_file(const std::string &path, std::string &error);

}  // namespace aos::exec::detail
