#pragma once

#include <algorithm>
#include <cstdio>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tool::cli {

inline std::string join(const std::vector<std::string> &values,
                        std::string_view separator = " ") {
    std::string result;
    for (const std::string &value : values) {
        if (!result.empty()) result.append(separator);
        result.append(value);
    }
    return result;
}

inline std::string truncate_utf8(std::string value, std::size_t limit) {
    if (value.size() <= limit) return value;
    std::size_t end = limit;
    while (end > 0 &&
           (static_cast<unsigned char>(value[end]) & 0xc0U) == 0x80U) {
        --end;
    }
    value.resize(end);
    return value;
}

inline void print_table(const std::vector<std::string> &headers,
                        const std::vector<std::vector<std::string>> &rows) {
    std::vector<std::size_t> widths(headers.size());
    for (std::size_t column = 0; column < headers.size(); ++column) {
        widths[column] = headers[column].size();
    }
    for (const auto &row : rows) {
        for (std::size_t column = 0;
             column < row.size() && column < widths.size(); ++column) {
            widths[column] = std::max(widths[column], row[column].size());
        }
    }
    auto print_row = [&](const std::vector<std::string> &row) {
        for (std::size_t column = 0; column < headers.size(); ++column) {
            const std::string &value = row[column];
            std::fwrite(value.data(), 1, value.size(), stdout);
            if (column + 1 != headers.size()) {
                const std::size_t padding = widths[column] - value.size() + 2;
                for (std::size_t index = 0; index < padding; ++index) {
                    std::fputc(' ', stdout);
                }
            }
        }
        std::fputc('\n', stdout);
    };
    print_row(headers);
    for (const auto &row : rows) print_row(row);
}

inline std::string json_escape(std::string_view value) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string escaped = "\"";
    for (const unsigned char character : value) {
        switch (character) {
            case '\"': escaped += "\\\""; break;
            case '\\': escaped += "\\\\"; break;
            case '\b': escaped += "\\b"; break;
            case '\f': escaped += "\\f"; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default:
                if (character < 0x20U) {
                    escaped += "\\u00";
                    escaped += digits[character >> 4U];
                    escaped += digits[character & 0x0fU];
                } else {
                    escaped += static_cast<char>(character);
                }
        }
    }
    escaped += '\"';
    return escaped;
}

inline std::string indent(std::string_view text, std::size_t spaces) {
    const std::string prefix(spaces, ' ');
    std::string result;
    std::size_t begin = 0;
    while (begin < text.size()) {
        const std::size_t newline = text.find('\n', begin);
        const std::size_t end =
            newline == std::string_view::npos ? text.size() : newline;
        result += prefix;
        result.append(text.substr(begin, end - begin));
        if (newline == std::string_view::npos) break;
        result += '\n';
        begin = newline + 1;
    }
    return result;
}

}  // namespace aos::tool::cli
