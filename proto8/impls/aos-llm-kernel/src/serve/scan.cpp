// scan.cpp：【serve】檢查排隊信件、挑選與解析 endpoint 能力包（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "aos/directive.hpp"
#include "aos/files.hpp"

#include <chrono>

namespace aos::llm_kernel {

// 查代號、解那組的指示詞、定 exec、讀包的 slots／budget／speed（填進 w）；查不到或那組壞了＝回那封信的 error 回信；
// request 撞到包釘死的（fixed 裡的 key、包有 model 而 request 寫 model）＝RequestBad（11-05 feat-proto 件 2）。
// pick 在 scan 驗過 request 是物件之後才叫。
std::optional<Json> Server::pick(Waiting& w) {
    const Json& body = w.letter["body"];
    if (body.contains("endpoint")) {
        w.endpoint = body["endpoint"].get<std::string>();
    } else if (cfg_.endpoint) {
        w.endpoint = *cfg_.endpoint;
    } else {
        return error_reply(code::EndpointMissing, "the letter has no endpoint (name) and kernel.json has no default endpoint");
    }
    if (!cfg_.endpoints.contains(w.endpoint)) {
        return error_reply(code::EndpointUnknown, "endpoint " + w.endpoint + " is not in kernel.json endpoints");
    }
    Json g;
    try {
        g = aos::resolve(cfg_.endpoints[w.endpoint], cfg_.endpoint_dirs.at(w.endpoint));
    } catch (const Error& e) {
        return error_reply(e.code, "kernel.json endpoints." + w.endpoint + ": " + e.msg);
    }
    if (!g.is_object()) {
        return error_reply(code::CfgBad, "kernel.json endpoints." + w.endpoint + " must be an object (llm settings), got " + aos::dumps(g));
    }
    w.exec = cfg_.exec;
    if (g.contains("exec")) {
        if (!g["exec"].is_string() || g["exec"].get<std::string>().empty()) {
            return error_reply(code::CfgBad, "kernel.json endpoints." + w.endpoint + ".exec must be a non-empty string, got " + aos::dumps(g["exec"]));
        }
        w.exec = target_abs(g["exec"].get<std::string>(), cfg_.base);
    }
    try {
        w.pack = parse_pack(g, w.endpoint);
    } catch (const Error& e) {
        return error_reply(e.code, e.msg);
    }
    std::optional<std::string> clash = fixed_clash(g, body["request"], w.endpoint);
    if (clash) {
        return error_reply(code::RequestBad, *clash);
    }
    w.group = strip_pack(g);   // kernel 看的 exec／slots／budget／speed 拿掉，其他原樣交給 endpoint 函數
    return std::nullopt;
}

std::vector<Waiting> Server::scan() {
    std::vector<Waiting> ws;
    double now = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    Json seen = Json::object();
    for (const std::string& id : aos::names_in(mb_.fresh(), true)) {
        std::string path = aos::join(aos::join(mb_.fresh(), id), "letter.json");
        std::optional<Json> letter = aos::read_json(path);
        if (!letter || !letter->is_object() || !letter->value("body", Json()).is_object() ||
            !(*letter)["body"].contains("request")) {
            std::string why = "cannot understand the letter: letter.json must be an N-16 letter with body = {\"endpoint\"?: name, \"request\": {...}, \"priority\"?}";
            refuse(id, error_reply(code::LetterBad, why));
            continue;
        }
        const Json& body = (*letter)["body"];
        if (body.contains("endpoint") && !body["endpoint"].is_string()) {
            refuse(id, error_reply(code::LetterBad, "letter body.endpoint must be a string (name), got " + aos::dumps(body["endpoint"])));
            continue;
        }
        Waiting w;
        w.id = id;
        w.letter = *letter;
        if (letter->value("sender", Json()).is_string()) {
            w.sender = (*letter)["sender"].get<std::string>();   // 信封的 sender（aos-post／aos-llm 寫的 identity()；不驗，10-15「先信任」）
        }
        try {
            w.priority = priority_of(*letter);
        } catch (const Error& e) {
            refuse(id, error_reply(code::LetterBad, "letter " + e.msg));
            continue;
        }
        const Json& req = body["request"];
        if (!req.is_object() || !req.value("messages", Json()).is_array()) {
            refuse(id, error_reply(code::RequestBad, "body.request must be an object and messages an array"));
            continue;
        }
        if (req.contains("stream") && !req["stream"].is_null() && req["stream"] != Json(false)) {
            refuse(id, error_reply(code::RequestBad, "streaming is not supported: request must not set stream: true"));
            continue;
        }
        std::optional<Json> bad = pick(w);
        if (bad) {
            refuse(id, *bad);
            continue;
        }
        if (w.priority.deadline && *w.priority.deadline < now) {
            refuse(id, error_reply(code::DeadlineMissed, "deadline passed before its turn; not run"));
            continue;
        }
        w.seen_at_runs = q_.runs;
        Json old = q_.seen_at_runs.value(id, Json());
        if (aos::is_count(old)) {
            w.seen_at_runs = old.get<long long>();
        }
        seen[id] = w.seen_at_runs;
        ws.push_back(w);
    }
    q_.seen_at_runs = seen;   // 只留還在排的
    return ws;
}

}  // namespace aos::llm_kernel
