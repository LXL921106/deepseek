#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单元门禁 · structural_invariant 层（TIM-01 – TIM-05）

判定（可阻断交付）:
  TIM-01  镜头编号从 01 起连续、不缺号不重号
  TIM-02  每个镜头都有可解析的「时长计算」，且末尾能读出该镜时长
  TIM-03  Σ 各镜时长 == 单元声明总秒数（「共N镜共X秒」与「总计X秒」一致）
  TIM-04  单元总秒数落在平台区间 6—15 秒（15 是上限不是目标）
  TIM-05  时长算式算术自洽：字数÷语速 向上取整到 0.5s，加缓冲后等于该镜时长

不做（reviewed / craft_default）:
  - 语速档位选得对不对（4/5/3 是默认，交审查者）
  - 镜头数、节奏、景别偏好
  - 成片里模型是否真的说了那么久（生成层，脚本管不了）

用法:
  python check_units.py --delivery 交付物.md [--json]
退出码: 0 = 通过；1 = 有阻断项；2 = 用法/读取错误
"""

import argparse
import json
import math
import re
import sys


# Windows 控制台默认 GBK：✅/❌ 会抛 UnicodeEncodeError，把门禁直接打崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

_UNIT = re.compile(r'^#*\s*单元\s*(\d+)')
_CLIP_LEGACY = re.compile(r'^#{2,4}\s*Clip\s*0*\d+', re.IGNORECASE)
_TOTAL_DECL = re.compile(r'共\s*(\d+)\s*镜共\s*([\d.]+)\s*秒')
_SUM_DECL = re.compile(r'总计[：:]\s*([\d.]+)\s*秒')
_SHOT = re.compile(r'^#*\s*镜头\s*(\d+)\s*[|｜]\s*(.*)$')
_DUR = re.compile(r'\*{0,2}时长计算\*{0,2}\s*[：:]\s*(.+)')
_EQ_END = re.compile(r'=\s*([\d.]+)\s*s')
_DIV = re.compile(r'(\d+)\s*字\s*÷\s*(\d+)\s*=\s*([\d.]+)\s*s')
_APPROX = re.compile(r'≈\s*([\d.]+)\s*s')
_BUF = re.compile(r'[＋+]\s*[^\d＋+\n]{0,10}?([\d.]+)\s*s')
_BUF_PARTS = re.compile(r'[＋+]\s*[^\d＋+\n]{0,10}?([\d.]+)\s*s?\s*[（(]\s*'
                        r'(?:标点停顿|表演与停顿|表演|停顿|口型缓冲|口型|情绪)\s*'
                        r'([\d.]+)\s*[＋+]\s*([\d.]+)\s*余量?')
_REACT = re.compile(r'反应(?:镜头)?\s*([\d.]+)\s*s')
_ACTION = re.compile(r'动作步长\s*([\d.]+)\s*s')
_EMO = re.compile(r'情绪\s*([\d.]+)\s*s')
_MM = re.compile(r'(?<![\d.])\d{2,3}\s*mm(?![\w])')

MIN_S, MAX_S = 6.0, 15.0


def ceil_half(x):
    return math.ceil(x * 2 - 1e-9) / 2


def parse(text):
    """返回 (units, has_unit, has_clip)。has_unit/has_clip 用于 FMT-01 格式守卫。"""
    lines = text.splitlines()
    units, cur = [], None
    has_unit = False
    has_clip = False
    for i, raw in enumerate(lines):
        if _CLIP_LEGACY.match(raw):
            has_clip = True
        m = _UNIT.match(raw)
        if m:
            cur = {'no': int(m.group(1)), 'lineno': i + 1, 'decl_shots': None,
                   'decl_total': None, 'sum_total': None, 'shots': []}
            units.append(cur)
            has_unit = True
            continue
        if cur is None:
            cur = {'no': 1, 'lineno': 1, 'decl_shots': None, 'decl_total': None,
                   'sum_total': None, 'shots': []}
            units.append(cur)
        m = _TOTAL_DECL.search(raw)
        if m:
            cur['decl_shots'] = int(m.group(1))
            cur['decl_total'] = float(m.group(2))
        m = _SUM_DECL.search(raw)
        if m:
            cur['sum_total'] = float(m.group(1))
        m = _SHOT.match(raw)
        if m:
            cur['shots'].append({'n': int(m.group(1)), 'lineno': i + 1,
                                 'head': (m.group(2) or '').strip(), 'dur': None,
                                 'div': None, 'approx': None, 'buf': None,
                                 'react': None, 'action': None})
            continue
        m = _DUR.search(raw)
        if m and cur['shots']:
            sh = cur['shots'][-1]
            sh['raw'] = m.group(1).strip()
            e = _EQ_END.findall(sh['raw'])
            if e:
                sh['dur'] = float(e[-1])
            else:
                # 反应镜「反应镜头 1.5s」/ 动作镜「动作步长 3.0s + 情绪1.0s」
                r0 = _REACT.search(sh['raw'])
                a0 = _ACTION.search(sh['raw'])
                if r0:
                    sh['dur'] = float(r0.group(1))
                elif a0:
                    emo = _EMO.search(sh['raw'])
                    sh['dur'] = float(a0.group(1)) + (float(emo.group(1)) if emo else 0.0)
            d = _DIV.search(sh['raw'])
            if d:
                sh['div'] = (int(d.group(1)), int(d.group(2)), float(d.group(3)))
            a = _APPROX.search(sh['raw'])
            if a:
                sh['approx'] = float(a.group(1))
            b = _BUF.search(sh['raw'])
            if b:
                sh['buf'] = float(b.group(1))
            r = _REACT.search(sh['raw'])
            if r:
                sh['react'] = float(r.group(1))
            act = _ACTION.search(sh['raw'])
            if act:
                sh['action'] = float(act.group(1))
    return units, has_unit, has_clip, text


def check(units, has_unit=True, has_clip=False, raw=''):
    blockers, warnings, info = [], [], []

    # CAM-04 提示词里不得出现焦距（mm）。
    # 「角色定位」写了「精通 ARRI/RED/Sony 全系列摄影机技术特性」——这会让模型想写机型与参数。
    # 而实测「近景＋85mm」会被执行成中远景（把不该入画的人也拍进来）。**摄影机的功力用在决定画面，不写在参数上。**
    mm = _MM.findall(raw)
    if mm:
        blockers.append({'id': 'CAM-04',
                         'msg': f'提示词里出现了焦距 {sorted(set(mm))}——`CAM-01` 要求只写景别，'
                                f'不写 mm（实测「近景＋85mm」被执行成中远景）'})

    # FMT-01/02 格式守卫：不认识就报错，不要静默通过
    # （实测教训：check_timeline 曾因找不到 `### Clip NN` 而一个分镜都没读到，把漏了 6 秒的提示词判成通过）
    if not has_unit:
        if has_clip:
            blockers.append({'id': 'FMT-01',
                             'msg': '交付物是**旧格式**（`### Clip NN`）。本渲染器已换主干为'
                                    '「单元 N + 镜头 N | + 时长计算」——请按新格式重写；'
                                    '若确实要审历史旧格式交付，请用 check_timeline.py'})
        elif any(u['shots'] for u in units):
            blockers.append({'id': 'FMT-03',
                             'msg': '是单元格式，但**缺 `单元 N` 标题行**——§10 要求每个单元以'
                                    '`单元 N` 单独一行打头（门禁才能识别这是第几个单元）'})
        else:
            blockers.append({'id': 'FMT-01',
                             'msg': '交付物里既没有「单元 N」也没有「### Clip NN」——'
                                    '**格式不认识，请人工确认**。不要因为脚本没报警就当作通过：'
                                    '它只是没读到内容'})

    if not units:
        warnings.append({'id': 'TIM-01', 'msg': '没有解析到「单元 N」结构'})

    for u in units:
        tag = f'单元 {u["no"]}'
        shots = u['shots']

        # TIM-01 编号连续
        if shots:
            nums = [s['n'] for s in shots]
            if nums != list(range(nums[0], nums[0] + len(nums))):
                blockers.append({'id': 'TIM-01', 'msg': f'{tag} 镜头编号不连续：{nums}'})
            elif len(set(nums)) != len(nums):
                blockers.append({'id': 'TIM-01', 'msg': f'{tag} 镜头编号有重复：{nums}'})

        # TIM-02 每镜有可解析时长
        for s in shots:
            if s['dur'] is None:
                blockers.append({'id': 'TIM-02',
                                 'msg': f'{tag} 镜头 {s["n"]:02d}（第 {s["lineno"]} 行）'
                                        f'「时长计算」缺失或末尾读不出 `= Xs`：{s.get("raw","(无)")[:40]}'})
            # TIM-05 算术自洽
            if s['div'] and s['dur'] is not None:
                n, rate, stated = s['div']
                if rate <= 0:
                    blockers.append({'id': 'TIM-05', 'msg': f'{tag} 镜头 {s["n"]:02d} 语速为 0'})
                    continue
                exact = n / rate
                step = ceil_half(exact)
                if s['approx'] is not None and abs(s['approx'] - step) > 1e-6:
                    blockers.append({'id': 'TIM-05',
                                     'msg': f'{tag} 镜头 {s["n"]:02d}：{n}字÷{rate}={exact:.2f}s，'
                                            f'向上取整到 0.5 应为 {step}s，写的是 {s["approx"]}s'})
                calc = (s['approx'] if s['approx'] is not None else step) + (s['buf'] or 0.0)
                if abs(calc - s['dur']) > 1e-6:
                    blockers.append({'id': 'TIM-05',
                                     'msg': f'{tag} 镜头 {s["n"]:02d}：朗读 {s["approx"]}s ＋ '
                                            f'表演/停顿 {s["buf"]}s = {calc}s，与写出的 {s["dur"]}s 不符'})

            # TIM-05 之二：括号里拆出来的加数，加起来必须等于写出来的加数。
            # 实测教训：写「加数2.0s（标点停顿1.1＋0.5余量）」，1.1＋0.5 只有 1.6——
            # 多出的 0.4s 不会被念出来，只会变成静默。
            bp = _BUF_PARTS.search(s.get('raw') or '')
            if bp:
                stated, pause, margin = float(bp.group(1)), float(bp.group(2)), float(bp.group(3))
                if abs(stated - (pause + margin)) > 1e-6:
                    over = round(stated - (pause + margin), 2)
                    blockers.append({'id': 'TIM-05',
                                     'msg': f'{tag} 镜头 {s["n"]:02d}：写「加数{stated}s」，但括号里 '
                                            f'{pause}＋{margin}={round(pause + margin, 2)}s——'
                                            f'多出的 {over}s 念不出来，只会变成静默'})
        # SHT-05 双对比切镜（**只提示，不阻断**）：相邻镜头不该景别和运镜都没变
        hd = [re.split(r'[|｜]', s['head']) for s in shots]
        for i in range(1, len(shots)):
            if len(hd[i]) < 2 or len(hd[i - 1]) < 2:
                continue
            size_a, size_b = hd[i - 1][0].strip(), hd[i][0].strip()
            move_a, move_b = hd[i - 1][1].strip(), hd[i][1].strip()
            if size_a == size_b and move_a == move_b:
                warnings.append({'id': 'SHT-05',
                                 'msg': f'{tag} 镜头 {shots[i-1]["n"]:02d}→{shots[i]["n"]:02d} '
                                        f'景别和运镜都没变（{size_b}｜{move_b}）——'
                                        f'双对比切镜要求至少换一项'})

        # 数字对账
        total = sum(s['dur'] for s in shots if s['dur'] is not None)
        if u['decl_total'] is not None and shots:
            if abs(total - u['decl_total']) > 1e-6:
                blockers.append({'id': 'TIM-03',
                                 'msg': f'{tag} 各镜时长合计 {total}s，与声明「共{u["decl_shots"]}镜共{u["decl_total"]}秒」不符'})
        if u['decl_shots'] is not None and shots and u['decl_shots'] != len(shots):
            blockers.append({'id': 'TIM-03',
                             'msg': f'{tag} 声明 {u["decl_shots"]} 镜，实际写出 {len(shots)} 镜'})
        if u['sum_total'] is not None and shots and abs(u['sum_total'] - total) > 1e-6:
            blockers.append({'id': 'TIM-03',
                             'msg': f'{tag} 结尾「总计 {u["sum_total"]} 秒」与实际合计 {total}s 不符'})

        # TIM-04 平台区间
        shown = u['decl_total'] if u['decl_total'] is not None else total
        if shots and shown:
            if shown > MAX_S + 1e-6:
                blockers.append({'id': 'TIM-04', 'msg': f'{tag} 总时长 {shown}s 超过平台上限 {MAX_S}s'})
            elif shown < MIN_S - 1e-6:
                blockers.append({'id': 'TIM-04',
                                 'msg': f'{tag} 总时长 {shown}s 低于平台下限 {MIN_S}s——并入相邻单元，或按 {MIN_S}s 设'})
            else:
                info.append(f'{tag}：{len(shots)} 镜共 {shown}s（平台可设）')

    return {'blockers': blockers, 'warnings': warnings, 'info': info,
            'fired': sorted({b['id'] for b in blockers}),
            'stats': {'units': len(units), 'shots': sum(len(u['shots']) for u in units)}}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--delivery', required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    try:
        txt = open(a.delivery, encoding='utf-8').read()
    except OSError as e:
        print(f'读取失败: {e}', file=sys.stderr)
        return 2

    r = check(*parse(txt))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        s = r['stats']
        print(f'单元门禁 · 单元 {s["units"]} 个 / 镜头 {s["shots"]} 个')
        print('-' * 60)
        if r['blockers']:
            print(f'❌ 阻断项 {len(r["blockers"])} 条（不得交付）:')
            for b in r['blockers']:
                print(f'   [{b["id"]}] {b["msg"]}')
        else:
            print('✅ 无阻断项')
        for w in r['warnings']:
            print(f'⚠️  [{w["id"]}] {w["msg"]}')
        for m in r['info']:
            print(f'ℹ️  {m}')
    return 1 if r['blockers'] else 0


if __name__ == '__main__':
    sys.exit(main())
