#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回归门禁（判定「没有退步」，不看戏写得怎么样）

对 evaluations/cases/ 下每个案例，运行全部校验脚本，核对门禁咬中的 ID 是否与 expected.json 一致：
  - must_fire 里的每一个 ID 都必须出现
  - must_not_fire 里的任何一个 ID 都不得出现

用法:
  python gate.py                 # 跑全部案例
  python gate.py --case 02-clean # 只跑一个
  python gate.py --verbose
退出码: 0 = 全部通过；1 = 有案例不符；2 = 环境错误

为什么要有这一层：
  只写着「检查过了」的散文规则，无法证明它还在生效。
  这个门禁把「规则 → 会不会真的拦住」变成可重复的判定。
"""

import argparse
import json
import os
import subprocess
import sys


# Windows 控制台默认 GBK：✅/❌ 会抛 UnicodeEncodeError，把门禁直接打崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, 'scripts')
CASES = os.path.join(HERE, 'cases')

CHECKERS = {
    'check_dialogue.py': ['--script', 'script.md', '--delivery', 'delivery.md', '--ledger', 'ledger.md'],
    'check_timeline.py': ['--delivery', 'delivery.md'],
    'check_cast.py': ['--delivery', 'delivery.md'],
    'check_units.py': ['--delivery', 'delivery.md'],
}


def run_checker(script, case_dir, verbose, exp=None):
    cmd = [sys.executable, os.path.join(SCRIPTS, script)]
    for tok in CHECKERS[script]:
        cmd.append(os.path.join(case_dir, tok) if tok.endswith('.md') else tok)
    if script == 'check_timeline.py' and exp and exp.get('clip_seconds'):
        cmd += ['--clip-seconds', str(exp['clip_seconds'])]
    cmd.append('--json')
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=60)
    except Exception as e:
        return None, f'运行失败: {e}'
    if p.returncode == 2:
        return None, f'用法/读取错误: {p.stderr.strip()}'
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        return None, f'输出不是 JSON: {p.stdout[:200]}'
    if verbose and data.get('info'):
        for m in data['info']:
            print(f'      ℹ️  {m}')
    return data.get('fired', []), None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--case', default=None)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    if not os.path.isdir(CASES):
        print(f'找不到案例目录: {CASES}', file=sys.stderr)
        return 2

    names = sorted(d for d in os.listdir(CASES) if os.path.isdir(os.path.join(CASES, d)))
    if a.case:
        names = [n for n in names if n == a.case]
    if not names:
        print('没有可运行的案例', file=sys.stderr)
        return 2

    total, failed = 0, 0
    for name in names:
        case_dir = os.path.join(CASES, name)
        exp_path = os.path.join(case_dir, 'expected.json')
        if not os.path.isfile(exp_path):
            print(f'⊘ {name}  跳过（缺 expected.json）')
            continue
        exp = json.load(open(exp_path, encoding='utf-8'))
        total += 1
        problems = []
        print(f'\n── {name} ── {exp.get("what","")}')
        for script in CHECKERS:
            if script in (exp.get('skip_checkers') or []):
                print(f'   ⊘ {script}  本案例不适用（skip_checkers）')
                continue
            must = set(exp.get('must_fire', {}).get(script, []))
            mustnot = set(exp.get('must_not_fire', []))
            fired, err = run_checker(script, case_dir, a.verbose, exp)
            if err:
                problems.append(f'{script}: {err}')
                print(f'   ✗ {script}: {err}')
                continue
            fset = set(fired)
            miss = must - fset
            extra = (mustnot & fset)
            if not miss and not extra:
                print(f'   ✓ {script}  咬中 {sorted(fset) or "（无，符合预期）"}')
            else:
                if miss:
                    problems.append(f'{script}: 应该咬中但没咬 → {sorted(miss)}')
                    print(f'   ✗ {script}  应该咬中但没咬: {sorted(miss)}')
                if extra:
                    problems.append(f'{script}: 不该咬中却咬了 → {sorted(extra)}')
                    print(f'   ✗ {script}  误报: {sorted(extra)}')
                print(f'      实际咬中: {sorted(fset)}')
        if problems:
            failed += 1
            print(f'   ⇒ FAIL')
        else:
            print(f'   ⇒ PASS')

    print('\n' + '=' * 60)
    print(f'回归门禁: {total - failed}/{total} 通过' + ('' if failed == 0 else f'  ❌ {failed} 个失败'))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
