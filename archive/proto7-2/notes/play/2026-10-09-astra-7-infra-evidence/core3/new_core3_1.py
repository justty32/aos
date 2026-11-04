"""Rerun: python3 proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/new_core3_1.py

Exit 1 expected on the affected version: pending reaping displays idle after restart.
"""
import sys
sys.dont_write_bytecode = True
from common import run_cases
from edges import restart_unknown

if __name__=='__main__':
    run_cases([('new-core3-1-confirm-%d'%i,restart_unknown) for i in range(1,4)])
