. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
WT=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528
cd "$S" || exit 1
g++ -std=c++20 -O0 -g -o probe probe.cpp \
  -I "$WT/core/inst/include" -I "$WT/common/include" -I "$WT/build/common/include" \
  -L "$WT/build/lib" -laos_inst -Wl,-rpath,"$WT/build/lib" 2>&1 | head -30
ls -l "$S/probe"
