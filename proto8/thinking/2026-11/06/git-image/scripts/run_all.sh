#!/bin/sh
# Run the full matrix sequentially; each benchmark cleans up its own trees.
set -eu
cd /tmp/i-team/sim
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 100 --commit-every 10 --mode A --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 10 --mode A --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 400 --commit-every 10 --mode A --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 1 --mode A --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 50 --mode A --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 100 --commit-every 10 --mode B --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 10 --mode B --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 400 --commit-every 10 --mode B --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 1 --mode B --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 50 --mode B --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 100 --commit-every 10 --mode C --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 10 --mode C --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 400 --commit-every 10 --mode C --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 1 --mode C --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 50 --mode C --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 100 --commit-every 10 --mode D --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 10 --mode D --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 400 --commit-every 10 --mode D --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 1 --mode D --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 50 --mode D --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 100 --commit-every 10 --mode A --archive --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 200 --commit-every 10 --mode A --archive --out results.jsonl
nice -n 19 python3 gitimage_bench.py --agents 50 --rounds 25 --commit-every 10 --mode A --archive --out results.jsonl
nice -n 19 python3 summarize.py
