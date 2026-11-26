// aos/fields.hpp：欄位表——一個檔的內容宣告成一個 struct，每個欄位只寫一次（X-macro），由它生出純文字（「名稱: 值」）與 json 兩種寫法。
//
// 純文字＝把 json 攤平：巢狀的名稱用 "." 接起來（procs_status 的 "<名>.<欄>" 就是這條）；空值寫 "-"（json 是 null）。
// 用法（每行結尾要接續行的反斜線，這裡省略）：
//   #define MY_FIELDS(F)
//       F(std::string, aos_name, Always)
//       F(long long, aos_pid, Always)
//       F(std::optional<long long>, code, Always)
//       F(std::string, external, OmitEmpty)
//       F(aos::procfs::Feedback, aos_ctl_, Embed)
//   AOS_RECORD(MyStatus, MY_FIELDS)
//   to_text(s) → "aos_name: x\naos_pid: 1\ncode: -\naos_ctl_cmd: -\n..."；to_json(s) → {"aos_name": "x", ...}
//
// 欄位的型別只收：std::string（空＝"-"／null）、整數、std::optional<那兩種>（沒有＝"-"／null）、
// 另一個 AOS_RECORD（json 是一層物件、純文字是 "名.欄"）、std::map<std::string, AOS_RECORD>（"鍵.欄"）。
// 第三格：Always 一定寫；OmitEmpty 空的（空字串、沒有值的 optional）整行不寫；
// Embed 只給 AOS_RECORD 用：把它的欄攤進這一層、名稱是「這一格的名字＋它的欄名」，不加 "."（例 aos_ctl_ ＋ cmd）。
// 型別裡有逗號（例 std::map<A, B>）時先取個 using 別名。
#pragma once

#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <type_traits>

namespace aos::procfs {

std::string kv_line(std::string_view name, std::string_view value);
std::string json_quote(std::string_view s);   // 加上引號、照 json 跳脫

enum class Show { Always, OmitEmpty, Embed };

#define AOS_RECORD_MEMBER_(type, name, show) type name{};
#define AOS_RECORD_VISIT_(type, name, show) v(#name, name, ::aos::procfs::Show::show);
#define AOS_RECORD(Name, LIST)                                     \
    struct Name {                                                  \
        LIST(AOS_RECORD_MEMBER_)                                   \
        template <class V>                                         \
        void visit(V&& v) const {                                  \
            LIST(AOS_RECORD_VISIT_)                                \
        }                                                          \
    };

namespace fields_detail {

template <class T> struct is_optional : std::false_type {};
template <class T> struct is_optional<std::optional<T>> : std::true_type {};
template <class T> struct is_map : std::false_type {};
template <class T> struct is_map<std::map<std::string, T>> : std::true_type {};
template <class T>
concept Record = requires(const T& t) { t.visit([](const char*, const auto&, Show) {}); };

// OmitEmpty 看的「空」：空字串、沒有值的 optional；其餘一律不空
template <class T>
bool is_empty(const T&) { return false; }
template <class T>
bool is_empty(const std::optional<T>& v) { return !v; }
inline bool is_empty(const std::string& v) { return v.empty(); }

inline std::string join(const std::string& base, std::string_view name) {
    return base.empty() ? std::string(name) : base + "." + std::string(name);
}

// ---------- 純文字 ----------
template <class T> void text(std::string& out, const std::string& key, const T& v);

// rec 的每一欄；concat＝名稱直接接在 base 後面（Embed），否則用 "." 接
template <Record R>
void text_fields(std::string& out, const std::string& base, bool concat, const R& rec) {
    rec.visit([&](const char* n, const auto& f, Show s) {
        if (s == Show::OmitEmpty && is_empty(f)) return;
        std::string key = concat ? base + n : join(base, n);
        if constexpr (Record<std::decay_t<decltype(f)>>) {
            if (s == Show::Embed) return text_fields(out, key, true, f);
        }
        text(out, key, f);
    });
}

template <class T>
void text(std::string& out, const std::string& key, const T& v) {
    if constexpr (Record<T>) text_fields(out, key, false, v);
    else if constexpr (is_map<T>::value)
        for (const auto& [k, x] : v) text(out, join(key, k), x);
    else if constexpr (is_optional<T>::value) {
        if (v) text(out, key, *v);
        else out += kv_line(key, "");
    } else if constexpr (std::is_same_v<T, std::string>) out += kv_line(key, v);
    else {
        static_assert(std::is_integral_v<T>, "field type not supported");
        out += kv_line(key, std::to_string(v));
    }
}

// ---------- json（一行、不縮排） ----------
template <class T> void json(std::string& out, const T& v);

template <Record R>
void json_fields(std::string& out, bool& first, const std::string& prefix, const R& rec) {
    rec.visit([&](const char* n, const auto& f, Show s) {
        if (s == Show::OmitEmpty && is_empty(f)) return;
        if constexpr (Record<std::decay_t<decltype(f)>>) {
            if (s == Show::Embed) return json_fields(out, first, prefix + n, f);
        }
        out += first ? "" : ", ";
        first = false;
        out += json_quote(prefix + n) + ": ";
        json(out, f);
    });
}

template <class T>
void json(std::string& out, const T& v) {
    if constexpr (Record<T>) {
        bool first = true;
        out += '{';
        json_fields(out, first, "", v);
        out += '}';
    } else if constexpr (is_map<T>::value) {
        out += '{';
        for (auto it = v.begin(); it != v.end(); ++it) {
            out += (it == v.begin() ? "" : ", ") + json_quote(it->first) + ": ";
            json(out, it->second);
        }
        out += '}';
    } else if constexpr (is_optional<T>::value) {
        if (v) json(out, *v);
        else out += "null";
    } else if constexpr (std::is_same_v<T, std::string>) out += v.empty() ? "null" : json_quote(v);
    else {
        static_assert(std::is_integral_v<T>, "field type not supported");
        out += std::to_string(v);
    }
}

}  // namespace fields_detail

// 純文字：一行一個「名稱: 值」，照欄位表的先後（map 照鍵排）
template <class T>
std::string to_text(const T& v) {
    std::string out;
    fields_detail::text(out, "", v);
    return out;
}

// json：一行，結尾一個換行
template <class T>
std::string to_json(const T& v) {
    std::string out;
    fields_detail::json(out, v);
    return out + "\n";
}

}  // namespace aos::procfs
