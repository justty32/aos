// cli.hpp：【cli】命令列 `aos-exec [旗標...] XXX [args...]`（公開介面 run_cli 在 aos/exec.hpp）。內部標頭。
//
//   cli.cpp   run_cli：解旗標（aos-util 的 parse_cli；旗標表目前有 --ws 與不帶值的 --dotenv-override）→ 一跳跳走（hop；字串轉向＝全新的一跳，
//             旗標不帶過去、args 原樣接過去、繞圈偵測沿用同一條 Chain）→ launch。自己的錯印一行「aos-exec: 代號 原因」、回 1
#pragma once

#include "common/common.hpp"
