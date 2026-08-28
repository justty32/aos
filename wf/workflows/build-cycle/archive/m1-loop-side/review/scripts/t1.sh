#!/bin/bash
W=/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-aadc15218d3266528
export PATH=$W/build/bin:$PATH
D=/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens1
cd "$D" || exit 1
rm -rf w1
mkdir w1
echo '$ aos init w1'
aos init w1
echo "[exit $?]"
echo '--- ls -1a w1 w1/.aos ---'
ls -1a w1 w1/.aos
echo '--- od -c w1/.aos/turn ---'
od -c w1/.aos/turn
echo '--- od -c w1/.aos/version ---'
od -c w1/.aos/version
echo '--- w1/.gitignore ? ---'
ls -la w1/.gitignore 2>&1
echo '$ aos --help'
aos --help
echo "[exit $?]"
