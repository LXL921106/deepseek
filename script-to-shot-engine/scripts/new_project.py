#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按模板建一个项目工作区。

用法:
  python new_project.py <目标目录> --title "剧名"

工作区承载跨会话状态：项目档案（参数／镜头偏好／工作流约定）与结尾状态链（逐组 结尾状态）。
已有内容的目标目录会被拒绝，不会覆盖。
退出码: 0 = 创建成功；2 = 用法或环境错误
"""

import argparse
import os
import shutil
import sys


# Windows 控制台默认 GBK：✅/❌ 会抛 UnicodeEncodeError，把门禁直接打崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), 'templates', 'project')


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('target', help='项目工作区目录')
    ap.add_argument('--title', default='', help='剧名，会替换模板里的 {剧名}')
    a = ap.parse_args()

    if not os.path.isdir(TEMPLATE):
        print(f'找不到模板: {TEMPLATE}', file=sys.stderr)
        return 2

    tgt = os.path.abspath(a.target)
    if os.path.isdir(tgt) and os.listdir(tgt):
        print(f'目标已存在且非空，未做任何改动: {tgt}', file=sys.stderr)
        return 2

    shutil.copytree(TEMPLATE, tgt, dirs_exist_ok=True)

    if a.title:
        for root, _dirs, files in os.walk(tgt):
            for fn in files:
                if not fn.endswith('.md'):
                    continue
                p = os.path.join(root, fn)
                with open(p, encoding='utf-8') as fh:
                    t = fh.read()
                if '{剧名}' in t:
                    with open(p, 'w', encoding='utf-8') as fh:
                        fh.write(t.replace('{剧名}', a.title))

    print(f'已创建项目工作区: {tgt}')
    for root, dirs, files in os.walk(tgt):
        dirs.sort()
        lvl = root[len(tgt):].count(os.sep)
        name = os.path.basename(root) or root
        print('  ' * lvl + name + '/')
        for f in sorted(files):
            print('  ' * (lvl + 1) + f)

    print()
    print('下一步：')
    print('  1. 把剧本与资产图放进 00-输入/')
    print('  2. 打开 01-档案/项目档案.md，逐项确认（尤其「镜头偏好」与「工作流约定」）')
    print('  3. 之后每次开工先读这份档案，再读 01-档案/结尾状态链.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
