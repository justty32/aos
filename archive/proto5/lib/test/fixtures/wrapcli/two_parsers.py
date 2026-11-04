"""wrap-cli fixture：兩個 ArgumentParser，分不出哪個是主的 → 全部拒收。"""
import argparse

a = argparse.ArgumentParser()
a.add_argument('--x')
b = argparse.ArgumentParser()
b.add_argument('--y')
