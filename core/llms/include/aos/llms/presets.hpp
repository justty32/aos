#pragma once

/* 內嵌 preset 的載入與列舉。 */

#include <aos/export.h>

#include <aos/llms/llm.hpp>

#include <string>
#include <vector>

namespace aos::llms {

enum class PresetState {
    Ok,
    InvalidArgument,
    IoError,
    JsonSyntax,
    InvalidFormat,
    UnknownPreset,
};

AOS_API const char *to_string(PresetState state) noexcept;
AOS_API PresetState load_preset(const std::string &id, LLM &out,
                                std::string &message);
AOS_API PresetState load_preset(const std::string &id, const char *path,
                                LLM &out, std::string &message);
AOS_API std::vector<std::string> preset_ids();

}  // namespace aos::llms
