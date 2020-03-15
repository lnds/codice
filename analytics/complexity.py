# based on https://github.com/adamtornhill/maat-scripts/blob/master/miner/complexity_calculations.py
import re

import numpy

from tools.encoding import detect_encoding

leading_tabs_expr =  re.compile(r'^(\t+)')
leading_spaces_expr = re.compile(r'^( +)')
empty_line_expr = re.compile(r'^\s*$')


def n_log_tabs(line):
    pattern = re.compile(r' +')
    wo_spaces = re.sub(pattern, '', line)
    m = leading_tabs_expr.search(wo_spaces)
    if m:
        tabs = m.group()
        return len(tabs)
    return 0


def n_log_spaces(line):
    pattern = re.compile(r'\t+')
    wo_tabs = re.sub(pattern, '', line)
    m = leading_spaces_expr.search(wo_tabs)
    if m:
        spaces = m.group()
        return len(spaces)
    return 0


def complexity_of(line):
    return n_log_tabs(line) + (n_log_spaces(line) / 4) # hardcoded indentation


def calculate_complexity_in(source):
    encoding = detect_encoding(source)
    with open(source, "r", newline='', encoding=encoding, errors='ignore') as file:
        source = file.read()
        lines_complexity = [complexity_of(line) for line in source.split("\n")]
        return numpy.mean(lines_complexity)