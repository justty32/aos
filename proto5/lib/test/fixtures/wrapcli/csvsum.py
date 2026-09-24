#!/usr/bin/env python3
"""wrap-cli 的 argparse fixture：各種 add_argument 寫法各一個；跑起來只把解析結果印成 JSON（測 argv 用）。"""
import argparse
import json


def main():
    p = argparse.ArgumentParser(description='Summarize the numeric columns of a CSV file.')
    p.add_argument('path', help='CSV file to read')
    p.add_argument('columns', nargs='*', help='columns to include (default: all)')
    p.add_argument('-d', '--delimiter', default=',', help='field delimiter')
    p.add_argument('--limit', type=int, default=10, help='max rows to show')
    p.add_argument('--ratio', type=float, help='sample ratio between 0 and 1')
    p.add_argument('--mode', choices=['sum', 'mean', 'max'], default='sum', help='how to combine values')
    p.add_argument('-v', '--verbose', action='count', default=0, help='more output (repeatable)')
    p.add_argument('--no-header', dest='header', action='store_false', help='the file has no header row')
    p.add_argument('--tag', action='append', help='tag the output (repeatable)')
    p.add_argument('--out', required=True, metavar='FILE', help='where to write the summary')
    p.add_argument('--strict', action='store_true', help='fail on bad rows')
    p.add_argument('--version', action='version', version='csvsum 1.0')
    args = p.parse_args()
    print(json.dumps(vars(args), sort_keys=True))


if __name__ == '__main__':
    main()
