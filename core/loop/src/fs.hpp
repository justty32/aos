#pragma once

#include <string>
#include <vector>

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
