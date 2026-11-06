// pack.cpp：【pack】endpoint 能力包（說明見 pack.hpp）。
#include "pack/pack.hpp"

#include "aos/util/io.hpp"
#include "aos/directive.hpp"
#include "aos/util/files.hpp"

namespace aos::llm_kernel {

static const char* const PACK_KEYS[] = {"exec", "slots", "budget", "speed"};

Pack parse_pack(const Json& g, const std::string& name) {
    Pack p;
    std::string at = "kernel.json endpoints." + name;
    Json s = g.value("slots", Json());
    if (!s.is_null()) {
        if (!aos::is_count(s) || s.get<long long>() < 1) {
            throw Error{code::CfgBad, at + ".slots must be a positive integer (letters of this endpoint in flight at once), got " + aos::dumps(s)};
        }
        p.slots = s.get<long long>();
        p.attrs["slots"] = s;
    }
    Json b = g.value("budget", Json());
    if (!b.is_null()) {
        if (!b.is_object()) {
            throw Error{code::CfgBad, at + ".budget must be {\"max_calls\", \"max_tokens\"}, got " + aos::dumps(b)};
        }
        for (const char* k : {"window", "spent"}) {
            if (b.contains(k)) {
                throw Error{code::CfgBad, at + ".budget." + k + " is not allowed: an endpoint budget uses the kernel's budget." + k +
                                              " (only max_calls, max_tokens here)"};
            }
        }
        for (const char* k : {"max_calls", "max_tokens"}) {
            Json x = b.value(k, Json());
            if (x.is_null()) {
                continue;
            }
            if (!aos::is_count(x)) {
                throw Error{code::CfgBad, at + ".budget." + k + " must be a non-negative integer (limit per window), got " + aos::dumps(x)};
            }
            (std::string(k) == "max_calls" ? p.max_calls : p.max_tokens) = x.get<long long>();
        }
    }
    Json sp = g.value("speed", Json());
    if (!sp.is_null()) {
        if (sp == "fast") {
            p.speed = 0;
        } else if (sp == "normal") {
            p.speed = 1;
        } else if (sp == "slow") {
            p.speed = 2;
        } else {
            throw Error{code::CfgBad, at + ".speed must be \"fast\", \"normal\" or \"slow\", got " + aos::dumps(sp)};
        }
        p.speed_name = sp.get<std::string>();
    }
    p.attrs["speed"] = p.speed_name;
    for (const char* k : {"cost", "context", "summary"}) {
        if (g.contains(k)) {
            p.attrs[k] = g[k];
        }
    }
    Json f = g.value("fixed", Json());
    if (!f.is_null() && !f.is_object()) {
        throw Error{code::CfgBad, at + ".fixed must be an object (sampling parameters pinned by this endpoint), got " + aos::dumps(f)};
    }
    return p;
}

Json strip_pack(Json g) {
    for (const char* k : PACK_KEYS) {
        g.erase(k);
    }
    return g;
}

std::optional<std::string> fixed_clash(const Json& g, const Json& request, const std::string& name) {
    std::string keys;
    const Json& f = g.contains("fixed") && g["fixed"].is_object() ? g["fixed"] : Json::object();
    int n = 0;
    for (auto& [k, v] : request.items()) {
        if (f.contains(k) || (k == "model" && g.contains("model"))) {
            keys += (n == 0 ? "" : ", ") + k;
            ++n;
        }
    }
    if (n == 0) {
        return std::nullopt;
    }
    return keys + (n == 1 ? " is" : " are") + " fixed by endpoint " + name + " (remove " + (n == 1 ? "it" : "them") +
           " from the request; to change " + (n == 1 ? "it" : "them") + " pick another endpoint name)";
}

std::map<std::string, Pack> read_packs(const Json& endpoints, const std::map<std::string, std::string>& dirs) {
    std::map<std::string, Pack> out;
    for (auto& [name, raw] : endpoints.items()) {
        try {
            aos::Resolved r = aos::resolve_keys(raw, dirs.at(name), {"slots", "budget", "speed", "cost", "context", "summary", "fixed"});
            if (!r.value.is_object()) {
                throw Error{code::CfgBad, "kernel.json endpoints." + name + " must be an object (llm settings), got " + aos::dumps(r.value)};
            }
            out[name] = parse_pack(r.value, name);
        } catch (const Error& e) {
            Pack p;
            p.error = e.code + " " + e.msg;
            out[name] = p;
        }
    }
    return out;
}

Json window_of(const std::map<std::string, Pack>& packs) {
    Json w = Json::object();
    for (const auto& [name, p] : packs) {
        if (p.error) {
            Json e = Json::object();
            e["error"] = *p.error;
            w[name] = e;
        } else {
            w[name] = p.attrs;
        }
    }
    return w;
}

}  // namespace aos::llm_kernel
