#include <aos/tooljson.hpp>

#include <algorithm>
#include <string_view>
#include <vector>

namespace aos::tooljson {
namespace {

std::size_t utf8_width(const unsigned char *data, std::size_t remaining) {
    const unsigned char first = data[0];
    if (first < 0x80) return 1;
    if (first >= 0xc2 && first <= 0xdf && remaining >= 2 &&
        (data[1] & 0xc0) == 0x80) {
        return 2;
    }
    if (first >= 0xe0 && first <= 0xef && remaining >= 3 &&
        (data[1] & 0xc0) == 0x80 && (data[2] & 0xc0) == 0x80 &&
        !(first == 0xe0 && data[1] < 0xa0) &&
        !(first == 0xed && data[1] >= 0xa0)) {
        return 3;
    }
    if (first >= 0xf0 && first <= 0xf4 && remaining >= 4 &&
        (data[1] & 0xc0) == 0x80 && (data[2] & 0xc0) == 0x80 &&
        (data[3] & 0xc0) == 0x80 && !(first == 0xf0 && data[1] < 0x90) &&
        !(first == 0xf4 && data[1] >= 0x90)) {
        return 4;
    }
    return 0;
}

std::vector<std::size_t> codepoint_offsets(const std::string &text) {
    std::vector<std::size_t> offsets;
    offsets.reserve(text.size() + 1);
    std::size_t at = 0;
    while (at < text.size()) {
        offsets.push_back(at);
        const auto *bytes =
            reinterpret_cast<const unsigned char *>(text.data() + at);
        const std::size_t width = utf8_width(bytes, text.size() - at);
        at += width == 0 ? 1 : width;
    }
    offsets.push_back(text.size());
    return offsets;
}

}  // namespace

std::string decode_output(const char *data, std::size_t size) {
    if (data == nullptr || size == 0) return {};
    if (std::find(data, data + size, '\0') != data + size) {
        return "(binary output, " + std::to_string(size) +
               " bytes, not shown)";
    }

    std::string out;
    out.reserve(size);
    const auto *bytes = reinterpret_cast<const unsigned char *>(data);
    std::size_t at = 0;
    while (at < size) {
        const std::size_t width = utf8_width(bytes + at, size - at);
        if (width == 0) {
            out += "\xef\xbf\xbd";
            ++at;
        } else {
            out.append(data + at, width);
            at += width;
        }
    }
    return out;
}

std::string clip_output(const std::string &text, const std::string &where,
                        std::size_t limit) {
    const std::vector<std::size_t> offsets = codepoint_offsets(text);
    const std::size_t characters = offsets.size() - 1;
    if (characters <= limit) return text;

    const std::size_t cut = characters - limit;
    if (where == "tail") {
        return "… [truncated, " + std::to_string(cut) +
               " earlier characters]\n" + text.substr(offsets[cut]);
    }
    return text.substr(0, offsets[limit]) + "\n… [truncated, " +
           std::to_string(cut) + " more characters]";
}

}  // namespace aos::tooljson
