#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时间戳门禁 · structural_invariant 层（TIM-01 – TIM-04）

判定（纯算术，本地可证明）:
  TIM-01  分镜标题符合 `分镜N（起-止秒）：`；每个 Clip 的首镜从 0 秒开始
  TIM-02  相邻分镜默认首尾相接，不留空；末镜结束在 Clip 总时长
  TIM-03  除注明「有意重叠」外，相邻分镜不得重叠
  TIM-04  Clip 声明的总时长 = 末镜结束时间

不做（属 craft_default，不阻断）:
  - 分镜该多长、该几个（TAS-02/03）
  - 分镜时长与内容量是否相称（TAS-01，reviewed_invariant）
  - 凝滞镜头是否合理

用法:
  python check_timeline.py --delivery 交付物.md
  python check_timeline.py --delivery 交付物.md --json

退出码: 0 = 通过；1 = 有阻断项；2 = 用法/读取错误
"""

import argparse
import json
import re
import sys

_CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def cn2int(s):
    if s.isdigit():
        return int(s)
    if s in _CN:
        return _CN[s]
    if s.startswith('十') and len(s) == 2:
        return 10 + _CN.get(s[1], 0)
    if len(s) == 2 and s[0] in _CN and s[1] == '十':
        return _CN[s[0]] * 10
    return None


_CLIP = re.compile(r'^#{2,4}\s*Clip\s*0*(\d+)\s*[｜|]?\s*(?:(\d+(?:\.\d+)?)\s*秒)?', re.IGNORECASE)
_SHOT_STRICT = re.compile(r'^\s*(?:分镜|镜头)\s*([一二三四五六七八九十\d]+)\s*[（(]\s*(\d+(?:\.\d+)?)\s*[-—~]\s*(\d+(?:\.\d+)?)\s*秒\s*[）)]\s*[：:]')
_SHOT_LOOSE = re.compile(r'^\s*(?:分镜|镜头)\s*([一二三四五六七八九十\d]+)\s*[（(]')
_OVERLAP_OK = re.compile(r'有意重叠|音画分离|音频桥|重叠区间')


def parse(text, declared=None):
    lines = text.splitlines()
    clips = []
    cur = None
    for i, raw in enumerate(lines):
        m = _CLIP.match(raw)
        if m:
            cur = {'no': int(m.group(1)), 'declared': float(m.group(2)) if m.group(2) else declared,
                   'lineno': i + 1, 'raw': raw.strip(), 'shots': []}
            clips.append(cur)
            continue
        if cur is None:
            # 真实交付里常常没有 `### Clip NN` 标题：整份文档当作一个 Clip
            cur = {'no': 1, 'declared': declared, 'lineno': 1,
                   'raw': '(无 Clip 标题，整份文档视为一个 Clip)', 'shots': []}
            clips.append(cur)
        m = _SHOT_STRICT.match(raw)
        if m:
            n = cn2int(m.group(1))
            cur['shots'].append({'n': n, 'start': float(m.group(2)), 'end': float(m.group(3)),
                                 'lineno': i + 1, 'overlap_ok': bool(_OVERLAP_OK.search(raw))})
            continue
        if _SHOT_LOOSE.match(raw):
            cur['shots'].append({'n': None, 'bad': True, 'lineno': i + 1, 'raw': raw.strip()[:48]})
    return clips


def check(clips):
    blockers, warnings, info = [], [], []
    if not clips:
        warnings.append({'id': 'TIM-01', 'msg': '没有解析到 `### Clip NN` 标题 + `分镜N（起-止秒）：` 结构'})

    for c in clips:
        tag = f'Clip {c["no"]:02d}'
        shots = c['shots']
        for s in shots:
            if s.get('bad'):
                blockers.append({'id': 'TIM-01', 'msg': f'{tag} 第 {s["lineno"]} 行标题不合格式（应形如 `分镜1（0-1.5秒）：`）：{s["raw"]}'})

        good = [s for s in shots if not s.get('bad')]
        if not good:
            continue

        # TIM-01 首镜从 0 开始
        if abs(good[0]['start']) > 1e-6:
            blockers.append({'id': 'TIM-01', 'msg': f'{tag} 首镜从 {good[0]["start"]} 秒开始，应从 0 秒开始（第 {good[0]["lineno"]} 行）'})

        # TIM-02/03 相邻关系
        for a, b in zip(good, good[1:]):
            gap = b['start'] - a['end']
            if gap > 1e-6:
                blockers.append({'id': 'TIM-02', 'msg': f'{tag} 第 {a["n"]}→{b["n"]} 镜之间有 {gap:.1f} 秒空档（{a["end"]}→{b["start"]}）'})
            elif gap < -1e-6:
                if b['overlap_ok']:
                    info.append(f'{tag} 第 {b["n"]} 镜与上一镜有意重叠 {abs(gap):.1f} 秒（已注明，TIM-03 通过）')
                else:
                    blockers.append({'id': 'TIM-03', 'msg': f'{tag} 第 {a["n"]}→{b["n"]} 镜重叠 {abs(gap):.1f} 秒但未注明「有意重叠」'})

        # TIM-04 总时长
        if c['declared'] is not None:
            if abs(good[-1]['end'] - c['declared']) > 1e-6:
                blockers.append({'id': 'TIM-04', 'msg': f'{tag} 声明 {c["declared"]} 秒，末镜结束在 {good[-1]["end"]} 秒'})
        else:
            warnings.append({'id': 'TIM-04',
                             'msg': f'{tag} 未声明总时长；分镜只覆盖 0—{good[-1]["end"]} 秒。'
                                    f'用 `--clip-seconds N` 复核末镜是否对齐：'
                                    f'**末镜短于 Clip 时长，多出来的那段时间会变成无声空白**'})

    return {'blockers': blockers, 'warnings': warnings, 'info': info,
            'fired': sorted({b['id'] for b in blockers}),
            'stats': {'clips': len(clips), 'shots': sum(len(c['shots']) for c in clips)}}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--delivery', required=True, help='交付物（提示词）文件')
    ap.add_argument('--clip-seconds', type=float, default=None,
                    help='这一段声明的总时长（秒）。提示词没有 `### Clip NN｜NN秒` 标题时必填，否则查不出"末镜短于 Clip 时长"')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    try:
        txt = open(a.delivery, encoding='utf-8').read()
    except OSError as e:
        print(f'读取失败: {e}', file=sys.stderr)
        return 2

    r = check(parse(txt, a.clip_seconds))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f'时间戳门禁 · Clip {r["stats"]["clips"]} 个 / 分镜 {r["stats"]["shots"]} 个')
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
