#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本号只在一个地方写，其余三处由本脚本同步。

为什么需要它：commit 标签推进了、`VERSION` 文件忘了改 —— 这个错已经犯过两次
（v4.0.0—v4.0.3 与 v4.1.0）。**规则写在文档里没人执行，就等于没有规则**，
所以把它变成一条可执行的命令。

用法:
  python release.py 4.1.0        # 写进四处
  python release.py --check      # 只检查四处是否一致（selfcheck 的 SC-01 也做这件事）
退出码: 0 = 一致/写入成功；1 = 不一致或写入失败
"""

import argparse
import os
import re
import sys


# Windows 控制台默认 GBK：✅/❌ 会抛 UnicodeEncodeError，把门禁直接打崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER_RE = r'\d+\.\d+\.\d+'


def read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def write(p, t):
    with open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(t)


def current():
    return read(os.path.join(ROOT, 'VERSION')).strip()


def views():
    """返回 [(说明, 文件, 正则, 期望匹配组)]，用于定位四处版本号。"""
    return [
        ('VERSION', 'VERSION', rf'^({VER_RE})\s*$', 1),
        ('SKILL.md 标题', 'SKILL.md', rf'^# Script-to-Shot Engine v({VER_RE})', 1),
        ('README.md 徽章', 'README.md', rf'version-({VER_RE})-', 1),
        ('README.md 页脚', 'README.md', rf'Current version <b>v({VER_RE})</b>', 1),
        ('README.zh-CN.md 徽章', 'README.zh-CN.md', rf'version-({VER_RE})-', 1),
        ('README.zh-CN.md 页脚', 'README.zh-CN.md', rf'当前版本 <b>v({VER_RE})</b>', 1),
    ]


def found():
    out = []
    for label, rel, pat, grp in views():
        m = re.search(pat, read(os.path.join(ROOT, rel)), re.M)
        out.append((label, rel, pat, found_num := (m.group(grp) if m else None)))
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('version', nargs='?')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()

    if a.check or not a.version:
        rows = found()
        vers = {v for _l, _r, _p, v in rows}
        for label, rel, _p, v in rows:
            print(f'  {"✅" if v == current() else "❌"} {label:<24} {v}   ({rel})')
        if len(vers) == 1 and None not in vers:
            print(f'四处一致：{vers.pop()}')
            return 0
        print(f'❌ 不一致：{sorted(str(x) for x in vers)}')
        return 1

    if not re.fullmatch(r'\d+\.\d+\.\d+', a.version):
        print(f'版本号格式不对：{a.version}（应为 X.Y.Z）', file=sys.stderr)
        return 1

    changed = 0
    for label, rel, pat, _grp in views():
        p = os.path.join(ROOT, rel)
        t = read(p)
        if not re.search(pat, t, re.M):
            print(f'❌ 找不到版本号位置：{label}（{rel}）', file=sys.stderr)
            return 1
        nt = re.sub(pat, lambda m: m.group(0).replace(m.group(1), a.version), t, count=1, flags=re.M)
        if nt != t:
            write(p, nt)
            changed += 1
        print(f'  ✅ {label:<24} → {a.version}')

    # 写回 VERSION 后再复查
    if current() != a.version:
        print('❌ VERSION 未写成功', file=sys.stderr)
        return 1
    print(f'版本已统一为 {a.version}（改了 {changed} 处）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
