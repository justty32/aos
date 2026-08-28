. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens2/env.sh
set -x
rm -rf "$S/w1"
mkdir -p "$S/w1"
"$AOS" init "$S/w1"
find "$S/w1" | sort
command -v strace
