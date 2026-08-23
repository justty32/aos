#pragma once

#include <aos/tooljson.hpp>

#include <catch2/catch_test_macros.hpp>

#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include <dirent.h>
#include <unistd.h>

inline std::string exec_spec(
    const std::string &name = "probe",
    const std::string &properties = R"("value":{"type":"string"})",
    const std::string &required = "[]",
    const std::string &recipe = R"("exec":["probe"],"argv":{})") {
    return "{\"type\":\"function\",\"function\":{\"name\":\"" + name +
           "\",\"description\":\"說明 " + name +
           "\",\"parameters\":{\"type\":\"object\",\"properties\":{" +
           properties + "},\"required\":" + required +
           "}},\"_extra\":{\"_version\":\"0.1.0\",\"_type\":\"exec\"," +
           recipe + "}}";
}

inline aos::tooljson::Spec parse_spec(const std::string &text,
                                      const char *base = "/tmp") {
    aos::tooljson::Spec spec;
    std::string message;
    INFO(message);
    REQUIRE(aos::tooljson::load(text.data(), text.size(), base, spec, message) ==
            aos::tooljson::SpecState::Ok);
    return spec;
}

inline std::string make_tooljson_temp_dir() {
    std::string pattern = "/tmp/aos_tooljson_test_XXXXXX";
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    REQUIRE(mkdtemp(buffer.data()) != nullptr);
    return buffer.data();
}

inline void write_tooljson_file(const std::string &path,
                                const std::string &content) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    REQUIRE(static_cast<bool>(output));
    output << content;
    REQUIRE(static_cast<bool>(output));
}

inline void remove_tooljson_tree(const std::string &path) {
    DIR *dir = opendir(path.c_str());
    if (dir != nullptr) {
        while (dirent *entry = readdir(dir)) {
            const std::string name = entry->d_name;
            if (name == "." || name == "..") continue;
            const std::string child = path + "/" + name;
            DIR *nested = opendir(child.c_str());
            if (nested != nullptr) {
                closedir(nested);
                remove_tooljson_tree(child);
            } else {
                std::remove(child.c_str());
            }
        }
        closedir(dir);
    }
    rmdir(path.c_str());
}

struct TooljsonTempDir {
    TooljsonTempDir() : path(make_tooljson_temp_dir()) {}
    ~TooljsonTempDir() { remove_tooljson_tree(path); }
    std::string path;
};
