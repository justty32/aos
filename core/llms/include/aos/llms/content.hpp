#pragma once

/* URL／API key 正規化與 content parts 純函式。 */

#include <aos/export.h>

#include <optional>
#include <string>
#include <vector>

namespace aos::llms {

AOS_API std::string normalize_base_url(const std::string &url);
AOS_API std::string endpoint_root_url(const std::string &url);
AOS_API std::string resolve_key(
    const std::optional<std::string> &key = std::nullopt);
AOS_API std::string encode_image_url(const std::string &path_or_url);
AOS_API std::string build_content_json(
    const std::optional<std::string> &prompt,
    const std::vector<std::string> &images);

}  // namespace aos::llms
