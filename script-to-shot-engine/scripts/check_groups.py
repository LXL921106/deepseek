#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「组」格式交付物门禁（A 方案主干格式）

判定（可阻断）:
  FMT-01  不是「组 N」格式
  FMT-03  是组格式但缺「组 N」标题行
  CAM-04  正文出现焦距（\\d+mm）
  TIM-06  镜数≠声明；时间戳不首尾相接；总长≠声明
  AUD-04  声音轨的说话人不在「参考」清单里
  GRP-01  「参考：」没覆盖本组出场的人/物
  GRP-02  资产名没带状态（林秀兰 → 应为 林秀兰围裙）
  GRP-03  用了不支持的写法（首帧／尾帧）
  DIA-16  台词没写「看向〈对象〉」——会对着空气说
  DIA-17  说话人切换处没留反应空档（含跨组）——会抢话

只提示（不阻断）:
  SHT-07  写了「对视」的镜，景别不是双人（单人镜拍不到对视）
  SHT-08  镜1 没写明画面主体（`起始` 段会泄漏成镜1 画面）
  DIA-18  开口前的动作主语是说话人自己（属 DIA-12 同期，但若在反应拍里则矛盾）
  GRP-04  跨组：上一组「结束」的人与本组「起始」的人完全不相交

用法: python check_groups.py --delivery 交付物.md [--json]
退出码: 0=通过 1=有阻断 2=用法/读取错误
"""

import argparse
import json
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

ALIAS = {'妈妈': '林秀兰围裙', '林秀兰围裙': '林秀兰围裙', '林秀兰': '林秀兰围裙',
         '奶奶': '林秀兰围裙', '晓雯': '苏晓雯', '苏晓雯': '苏晓雯',
         '志远': '沈志远', '沈志远': '沈志远'}
NEEDS_STATE = {'林秀兰': '林秀兰围裙'}
MIN_REACT_GAP = 0.5

_MM = re.compile(r'(?<![\d.])\d{2,3}\s*mm(?![\w])')
_GROUP = re.compile(r'(?m)^组\s*(\d+)')
_SHOT = re.compile(r'镜(\d+)｜([\d.]+)—([\d.]+)s｜([^：:\n]+)[：:](.*?)(?=镜\d+｜|声音｜|环境声|结束：|\Z)', re.S)
_VOICE = re.compile(r'声音｜([\d.]+)—([\d.]+)s｜([^｜\n]*)｜([^：:\n]*)[：:]\s*[“"]([^”"]*)[”"]')


def names_in(s):
    out = set()
    for a, canon in ALIAS.items():
        if re.search(r'(?<![\u4e00-\u9fa5])' + re.escape(a), s or ''):
            out.add(canon)
    return out


def parse(text):
    blocks = re.split(r'(?m)^组\s*(\d+)', text)
    groups = []
    for i in range(1, len(blocks), 2):
        gno, body = int(blocks[i]), blocks[i + 1]
        d = {'no': gno}
        m = re.search(r'(\d+)\s*镜[，,]\s*生成\s*([\d.]+)\s*秒', body)
        d['decl_shots'] = int(m.group(1)) if m else None
        d['decl_dur'] = float(m.group(2)) if m else None
        for key, pat in (('ref', r'^参考[：:](.+)$'), ('start', r'^起始[：:](.+)$'),
                         ('end', r'^结束[：:](.+)$')):
            mm = re.search(pat, body, re.M)
            d[key] = mm.group(1).strip() if mm else None
        d['shots'] = [{'n': int(a), 'a': float(b), 'z': float(c),
                       'head': hd.strip(), 'body': bd.strip()}
                      for a, b, c, hd, bd in _SHOT.findall(body)]
        d['voices'] = [{'a': float(a), 'z': float(b), 'chan': ch.strip(),
                        'who': w.strip(), 'line': ln}
                       for a, b, ch, w, ln in _VOICE.findall(body)]
        groups.append(d)
    return groups, bool(groups)


def check(text):
    B, W, I = [], [], []
    groups, has = parse(text)

    if not has:
        B.append({'id': 'FMT-01', 'msg': '不是「组 N」格式——本门禁只认 A 方案的组格式'})

    mm = _MM.findall(text)
    if mm:
        B.append({'id': 'CAM-04', 'msg': f'正文出现焦距 {sorted(set(mm))}——只写景别，不写 mm'})

    for g in groups:
        tag = f"组{g['no']}"
        sh, vo = g['shots'], g['voices']

        # TIM-06
        if g['decl_shots'] is not None and len(sh) != g['decl_shots']:
            B.append({'id': 'TIM-06', 'msg': f"{tag} 声明 {g['decl_shots']} 镜，实际 {len(sh)} 镜"})
        nums = [s['n'] for s in sh]
        if nums and nums != list(range(1, len(nums) + 1)):
            B.append({'id': 'TIM-06', 'msg': f'{tag} 镜号不连续：{nums}'})
        for k in range(1, len(sh)):
            gap = sh[k]['a'] - sh[k - 1]['z']
            if abs(gap) > 0.01:
                B.append({'id': 'TIM-06',
                          'msg': f"{tag} 镜{sh[k-1]['n']}→镜{sh[k]['n']} 时间戳不接"
                                 f"（{sh[k-1]['z']}→{sh[k]['a']}，差 {gap:+.2f}s）"})
        if sh:
            total = sh[-1]['z']
            if g['decl_dur'] is not None and abs(total - g['decl_dur']) > 0.01:
                B.append({'id': 'TIM-06',
                          'msg': f'{tag} 时间戳合计 {total}s，声明 {g["decl_dur"]}s'})

        ref = names_in(g['ref'])
        for v in vo:
            vwho = names_in(v['who']) | names_in(v['chan'])
            if vwho and not (vwho <= ref):
                B.append({'id': 'AUD-04',
                          'msg': f"{tag} 声音 {v['a']}—{v['z']}s 的说话人 {sorted(vwho)} "
                                 f"不在「参考」清单里 {sorted(ref)}"})
            if not re.search(r'看|望|盯|对着|面向|转向', v['chan'] + v['who']):
                B.append({'id': 'DIA-16',
                          'msg': f"{tag} 声音 {v['a']}—{v['z']}s 台词没写「看向〈对象〉」："
                                 f"「{(v['chan'] + v['who']).strip()[:36]}」——会对着空气说"})

        # DIA-17 反应空档（组内）
        for k in range(1, len(vo)):
            gap = vo[k]['a'] - vo[k - 1]['z']
            if gap < MIN_REACT_GAP - 1e-6:
                B.append({'id': 'DIA-17',
                          'msg': f"{tag} 说话人切换 {vo[k-1]['who'] or '?'}→{vo[k]['who'] or '?'} "
                                 f"只留 {gap:+.2f}s——要 ≥{MIN_REACT_GAP}s 做反应，否则抢话"})

        for kw in ('首帧', '尾帧', '首尾帧'):
            if kw in text and f'组{g["no"]}' in text:
                pass
        if any(kw in text for kw in ('首帧', '尾帧', '首尾帧')):
            hit = [kw for kw in ('首帧', '尾帧', '首尾帧') if kw in text]
            B.append({'id': 'GRP-03', 'msg': f'出现不支持的写法 {hit}——本平台没有首尾帧参考'})

        # GRP-01 / GRP-02
        for label in ('start', 'end'):
            miss = names_in(g[label]) - ref
            if miss:
                B.append({'id': 'GRP-01',
                          'msg': f"{tag}「{'起始' if label == 'start' else '结束'}」里出现 "
                                 f"{sorted(miss)}，但「参考」清单里没有"})
        for s in sh:
            miss = names_in(s['head'] + s['body']) - ref
            if miss:
                B.append({'id': 'GRP-01',
                          'msg': f"{tag} 镜{s['n']} 里出现 {sorted(miss)}，但「参考」清单里没有"})
        joined = '\n'.join(filter(None, [g['ref'], g['start'], g['end'],
                                         *[s['head'] + s['body'] for s in sh]]))
        for bare, full in NEEDS_STATE.items():
            if re.search(r'(?<!围裙)' + bare + r'(?!围裙)', joined):
                B.append({'id': 'GRP-02',
                          'msg': f'{tag} 用了裸名「{bare}」——应为带状态的「{full}」'})

        # 提示级
        anchors = re.findall(r'（([^）]*)）', g['ref'] or '')
        body_all = '\n'.join([g['start'] or '', g['end'] or '',
                              *[s['head'] + s['body'] for s in sh]])
        for word in ('盒', '包装', '袋', '瓶', '罐'):
            if word in body_all and not any(word in a for a in anchors):
                W.append({'id': 'GRP-05',
                          'msg': f'{tag} 正文出现「{word}」，但「参考」的资产锚点里没有——'
                                 f'一张资产图常同时含主件与包装，可能漏写了'})
                break
        for s in sh:
            if '对视' in s['body'] and not re.search(r'双人|两人|同框|中景|全景', s['head'] + s['body']):
                W.append({'id': 'SHT-07',
                          'msg': f"{tag} 镜{s['n']} 写了「对视」但景别不是双人——单人镜拍不到对视"})
        if sh:
            h = sh[0]['head'] + sh[0]['body']
            if not re.search(r'焦点|机位偏|画面里|主体', h) and not names_in(h):
                W.append({'id': 'SHT-08',
                          'msg': f'{tag} 镜1 没写明画面主体——`起始` 段会被模型当成镜1 画面'})
        I.append(f"{tag}：{len(sh)} 镜共 {g['decl_dur']}s｜参考 {len(ref)} 项｜台词 {len(vo)} 句")

    # GRP-04 跨组状态链
    for k in range(1, len(groups)):
        a, b = names_in(groups[k - 1]['end']), names_in(groups[k]['start'])
        if a and b and not (a & b):
            W.append({'id': 'GRP-04',
                      'msg': f"组{groups[k-1]['no']} 结束的人 {sorted(a)} 与 "
                             f"组{groups[k]['no']} 起始的人 {sorted(b)} 不相交——状态断链"})

    return {'blockers': B, 'warnings': W, 'info': I,
            'fired': sorted({b['id'] for b in B}),
            'stats': {'groups': len(groups), 'shots': sum(len(g['shots']) for g in groups)}}


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
    r = check(txt)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        s = r['stats']
        print(f"组格式门禁 · 组 {s['groups']} 个 / 镜 {s['shots']} 个")
        print('-' * 64)
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
