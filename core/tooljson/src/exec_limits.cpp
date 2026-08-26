#include "exec_internal.hpp"

#include <string>
#include <utility>
#include <vector>

namespace aos::tooljson {
namespace {

using json = nlohmann::json;

}  // namespace

namespace detail {

SpecState parse_exec_limits(const Spec::Impl *impl, ExecBody *body,
                            std::string &message) {
    const json &extra = impl->extra;

    const auto ok = extra.find("ok_exit");
    if (ok != extra.end()) {
        if (!ok->is_array()) {
            return bad("_extra.ok_exit 要是整數 list", message);
        }
        std::vector<std::int64_t> exits;
        for (const json &item : *ok) {
            std::int64_t value = 0;
            if (!integer_value(item, value)) {
                return bad("_extra.ok_exit 要是整數 list", message);
            }
            exits.push_back(value);
        }
        if (!exits.empty()) body->ok_exit = std::move(exits);
    }

    const auto timeout = extra.find("timeout");
    if (timeout != extra.end()) {
        if (!finite_number(*timeout, body->timeout) || body->timeout <= 0) {
            return bad("_extra.timeout 要是大於 0 的有限秒數", message);
        }
    }

    const auto cwd = extra.find("cwd");
    if (cwd != extra.end() && !cwd->is_null()) {
        if (!cwd->is_string() || cwd->get_ref<const std::string &>().empty()) {
            return bad("_extra.cwd 要嘛是 null，要嘛是非空路徑字串", message);
        }
        body->cwd = detail::resolve_path(cwd->get<std::string>(), impl->base_dir);
    }

    const auto limits = extra.find("limits");
    if (limits != extra.end() && !limits->is_null()) {
        if (!limits->is_object()) {
            return bad("_extra.limits 要是 object", message);
        }
        body->limits = *limits;
    } else {
        body->limits = json::object();
    }

    std::vector<std::string> unknown_limits;
    for (auto it = body->limits.begin(); it != body->limits.end(); ++it) {
        if (!impl->properties.contains(it.key())) unknown_limits.push_back(it.key());
    }
    if (!unknown_limits.empty()) {
        return bad("_extra.limits 有未知參數 " +
                       detail::string_list_repr(unknown_limits),
                   message);
    }
    for (auto it = body->limits.begin(); it != body->limits.end(); ++it) {
        const std::string &name_value = it.key();
        const json &rule = it.value();
        if (!rule.is_object()) {
            return bad("_extra.limits['" + name_value + "'] 要是 object",
                       message);
        }
        const std::vector<std::string> unknown =
            unknown_keys(rule, {"max_bytes", "min", "max"});
        if (!unknown.empty()) {
            return bad("_extra.limits['" + name_value +
                           "'] 有不認得的鍵 " +
                           detail::string_list_repr(unknown),
                       message);
        }
        const auto cap = rule.find("max_bytes");
        if (cap != rule.end()) {
            const bool valid =
                (cap->is_number_unsigned()) ||
                (cap->is_number_integer() && cap->get<std::int64_t>() >= 0);
            if (!valid) {
                return bad("_extra.limits['" + name_value +
                               "'].max_bytes 要是非負整數",
                           message);
            }
        }
        double low = 0;
        double high = 0;
        const auto low_it = rule.find("min");
        const auto high_it = rule.find("max");
        const bool has_low = low_it != rule.end();
        const bool has_high = high_it != rule.end();
        if (has_low && !finite_number(*low_it, low)) {
            return bad("_extra.limits['" + name_value + "'].min 要是數字",
                       message);
        }
        if (has_high && !finite_number(*high_it, high)) {
            return bad("_extra.limits['" + name_value + "'].max 要是數字",
                       message);
        }
        if (has_low && has_high && low > high) {
            return bad("_extra.limits['" + name_value +
                           "'] 的 min 不可大於 max",
                       message);
        }
    }

    const auto source = extra.find("source");
    if (source != extra.end() && !source->is_null()) {
        if (!source->is_object()) {
            return bad("_extra.source 要是 object", message);
        }
        const auto size = source->find("size");
        if (size != source->end()) {
            const bool valid = size->is_number_unsigned() ||
                               (size->is_number_integer() &&
                                size->get<std::int64_t>() >= 0);
            if (!valid) {
                return bad("_extra.source.size 要是非負整數", message);
            }
        }
        const auto mtime = source->find("mtime");
        std::int64_t ignored_mtime = 0;
        if (mtime != source->end() && !integer_value(*mtime, ignored_mtime)) {
            return bad("_extra.source.mtime 要是整數", message);
        }
        const auto sha256 = source->find("sha256");
        if (sha256 != source->end() && !sha256->is_string()) {
            return bad("_extra.source.sha256 要是字串", message);
        }
    }

    return SpecState::Ok;
}

}  // namespace detail
}  // namespace aos::tooljson
