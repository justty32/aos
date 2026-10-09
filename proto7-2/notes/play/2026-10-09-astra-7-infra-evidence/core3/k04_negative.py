"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/k04_negative.py

Calibration only: simulate absent rescan in memory and demonstrate true two-generation detection.
"""
import sys
sys.dont_write_bytecode = True
from common import run_cases
from k04 import probe
if __name__=='__main__':
    run_cases([('k04-negative-control',lambda c:probe(c,negative_control=True))])
