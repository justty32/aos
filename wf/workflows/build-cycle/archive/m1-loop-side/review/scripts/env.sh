AOS=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528/build/bin/aos
LAB=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3
export AOS LAB
mkworld() { rm -rf "$1"; mkdir -p "$1"; "$AOS" init "$1" >/dev/null 2>&1 || echo INIT_FAIL; }
