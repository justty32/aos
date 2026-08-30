#include <aos/tick.hpp>

#include <nlohmann/json.hpp>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>

namespace aos::tick {

bool heartbeat_init(const loop::Layout &layout, Instant now,
                    std::uint64_t every_ms, std::string &error) {
    error.clear();
    if (!loop::ensure_layout(layout, error)) return false;

    const Paths paths = paths_of(layout);
    Config config;
    if (!read_config(paths.config_file, config, error)) return false;
    if (!ensure_heartbeat(paths, now, config.tz, error)) return false;

    nlohmann::ordered_json json = {
        {"id", "tick"},
        {"argv", nlohmann::ordered_json::array({"aos", "tick"})},
        {"every_ms", every_ms},
    };
    const std::string path = layout.every + "/tick.json";
    const std::string temporary = path + ".tmp";
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) {
            error = "無法開啟暫存檔 " + temporary;
            return false;
        }
        output << json.dump(2) << '\n';
        output.close();
        if (!output) {
            error = "無法寫入暫存檔 " + temporary;
            std::remove(temporary.c_str());
            return false;
        }
    }
    if (std::rename(temporary.c_str(), path.c_str()) != 0) {
        error = "無法發佈 " + path + ": " + std::strerror(errno);
        std::remove(temporary.c_str());
        return false;
    }
    return true;
}

}  // namespace aos::tick
