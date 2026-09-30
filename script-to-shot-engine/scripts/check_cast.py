#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在场人物门禁 · structural_invariant 层（CNT-05 / CNT-06）

判定（可阻断交付）:
  CNT-05  空间站位必须写成「画面从左到右」的有序排列；排列里的人名不得重复，且必须都在参考素材里登记
  CNT-06  每个分镜必须写「在场人物：…」，且在场人物必须是排列里出现过的名字

不做（reviewed / craft_default）:
  - 排列里的人数是否合适
  - 相对方位描述是否合理 —— CNT-05 已把格式改成"只能写排列"，**矛盾在语法上不可表达**
  - 成片里模型是否真的只画了这么多人（生成层，脚本管不了）

用法:
  python check_cast.py --delivery 交付物.md [--json]
退出码: 0 = 通过；1 = 有阻断项；2 = 用法/读取错误
"""

import argparse
import json
import re
import sys

_U8 = 'utf-8'

_REF = re.compile(r'参考素材[：:]\s*(.+)')
_AT = re.compile(r'@([^\s<（(；;，,、"”]+)')
_ARR = re.compile(r'【起始排列[^】]*】\s*([^\n【]*)')
_ARR_ALT = re.compile(r'起始排列[^：:]*[：:]\s*([^\n【]*)')
_AFTER = re.compile(r'走位后排列\s*([^\n【]*)')
_PRESENT = re.compile(r'在场人物[：:]\s*([^\n【]*)')
_SHOT = re.compile(r'^\s*(?:分镜|镜头)\s*([一二三四五六七八九十\d]+)\s*[（(]')

_SPLIT = re.compile(r'[｜|·、，,]+')


def names_of(seg, known=None):
    """把一段排列/在场人物文本拆成人名列表。"""
    out = []
    for raw in _SPLIT.split(seg or ''):
        t = raw.strip()
        if not t:
            continue
        t = re.split(r'[（(]', t)[0].strip()
        if not t:
            continue
        # 只保留人名（去掉"双人同框""无台词"这类说明）
        if known and t not in known:
            hit = [k for k in known if k in t]
            if not hit:
                continue
            t = max(hit, key=len)
        out.append(t)
    return out


def check(text):
    blockers, warnings, info = [], [], []
    lines = text.splitlines()

    # 参考素材里登记的 @名
    ref = []
    for raw in lines:
        m = _REF.search(raw)
        if m:
            ref = _AT.findall(m.group(1))
            break
    if not ref:
        warnings.append({'id': 'CNT-05', 'msg': '没有解析到「参考素材：」行，无法核对人名是否登记'})

    # 起始排列
    arr_txt = ''
    for raw in lines:
        m = _ARR.search(raw) or _ARR_ALT.search(raw)
        if m:
            arr_txt = m.group(1)
            break
    if not arr_txt:
        blockers.append({'id': 'CNT-05',
                         'msg': '空间站位没有写成「【起始排列·画面从左到右】A｜B｜C」——'
                                '相对方位描述（"某某坐在两人中间"）可以互相矛盾，模型会用多造一个人来同时满足'})
        arrange = []
    else:
        arrange = names_of(arr_txt, ref)
        if len(arrange) != len(set(arrange)):
            dup = [n for n in arrange if arrange.count(n) > 1]
            blockers.append({'id': 'CNT-05', 'msg': f'起始排列里有重复的人名：{sorted(set(dup))}'})
        unknown = [n for n in arrange if ref and n not in ref]
        if unknown:
            blockers.append({'id': 'CNT-05', 'msg': f'起始排列里出现参考素材未登记的人名：{unknown}'})
        info.append(f'起始排列（左→右）：{" ｜ ".join(arrange)}　共 {len(arrange)} 人')

    # 走位后排列（只改顺序，不改人数）
    for i, raw in enumerate(lines):
        m = _AFTER.search(raw)
        if m:
            after = names_of(m.group(1), ref)
            if after and arrange and sorted(after) != sorted(arrange):
                blockers.append({'id': 'CNT-07',
                                 'msg': f'第 {i+1} 行的「走位后排列」人数或成员变了：{after} ≠ {arrange}。'
                                        f'走位只改顺序，不改人数'})
            elif after:
                info.append(f'走位后排列（第 {i+1} 行）：{" ｜ ".join(after)}')

    # 逐分镜在场人物
    cur, shots = None, []
    for i, raw in enumerate(lines):
        m = _SHOT.match(raw)
        if m:
            cur = {'n': m.group(1), 'lineno': i + 1, 'present': None, 'raw': raw.strip()[:40]}
            shots.append(cur)
            # 不 continue：同一行末尾可能就跟着「在场人物：…」
        if cur is not None:
            m2 = _PRESENT.search(raw)
            if m2:
                cur['present'] = names_of(m2.group(1), ref)
                cur['present_lineno'] = i + 1

    if shots:
        missing = [s for s in shots if s['present'] is None]
        for s in missing:
            blockers.append({'id': 'CNT-06',
                             'msg': f'分镜{s["n"]}（第 {s["lineno"]} 行）没有写「在场人物：…」'})
        for s in shots:
            if not s['present']:
                continue
            if arrange:
                extra = [n for n in s['present'] if n not in arrange]
                if extra:
                    blockers.append({'id': 'CNT-06',
                                     'msg': f'分镜{s["n"]} 的在场人物出现排列之外的人：{extra}'
                                            f'（排列只有 {arrange}）'})
            if len(s['present']) != len(set(s['present'])):
                blockers.append({'id': 'CNT-06', 'msg': f'分镜{s["n"]} 的在场人物里同一个人出现两次'})
        info.append(f'分镜 {len(shots)} 个，在场人物：' +
                    '；'.join(f'{s["n"]}={len(s["present"] or [])}人' for s in shots))
    else:
        warnings.append({'id': 'CNT-06', 'msg': '没有解析到 `分镜N（起-止秒）：` 标题，逐镜在场人物未核对'})

    return {'blockers': blockers, 'warnings': warnings, 'info': info,
            'fired': sorted({b['id'] for b in blockers}),
            'stats': {'ref': len(ref), 'arrange': len(arrange), 'shots': len(shots)}}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--delivery', required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    try:
        txt = open(a.delivery, encoding=_U8).read()
    except OSError as e:
        print(f'读取失败: {e}', file=sys.stderr)
        return 2

    r = check(txt)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        s = r['stats']
        print(f'在场人物门禁 · 参考素材 {s["ref"]} 项 / 排列 {s["arrange"]} 人 / 分镜 {s["shots"]} 个')
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
