for t in strace ltrace perf sysdig bpftrace gdb; do printf '%s: ' "$t"; command -v "$t" || echo MISSING; done
ls /usr/bin | grep -i -E 'trace|ptrace' | head -20
