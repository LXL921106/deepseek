#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""镜头完整性门禁 · structural_invariant 层（CNT-05 – CNT-09）

对应 wan-renderer.md 的 §4 场景锚点 / §8 物理与表演 / §9 单镜模板。

判定（可阻断交付）:
  CNT-05  每个镜头都有「出场人物」，且至少一人
  CNT-06  出场人物里的角色都在单元「人物：」行登记过（禁造人）
  CNT-07  锚点名必须在本单元出现过的锚点集合里（禁 A1/B2 编号式匿名锚点）
  CNT-08  越肩镜必须写「同人声明」——前景与主体是两个不同的人；若前景就是画面里的同一个人，
          必须在声明里写明「同一个人／只出现一次／不是第二个人」，否则模型会画成两个人
  CNT-09  同一镜的「出场人物」不得重复列出同一个角色

只提示不阻断（固定词表不得阻断交付）:
  W-方位  画面描述里出现无参照方位词（左边/右边/旁边/对面）——规范铁律要求"锚点名+画左/画中/画右"
  W-心理  画面描述里出现心理感受（感到/心里/觉得/难过/悲伤/感动）——规范要求"看图说话，只写看得见的"

用法:
  python check_cast.py --delivery 交付物.md [--json]
退出码: 0 = 通过；1 = 有阻断项；2 = 用法/读取错误
"""

import argparse
import json
import re
import sys

_UNIT = re.compile(r'^#*\s*单元\s*(\d+)')
_SHOT = re.compile(r'^#*\s*镜头\s*(\d+)\s*[|｜]\s*(.*)$')
_CAST = re.compile(r'出场人物\s*[：:]\s*(.+)')
_SAME = re.compile(r'同人声明\s*[：:]\s*(.+)')
_ANCHOR_INLINE = re.compile(r'锚点\s*[：:]\s*([^）)]+)')
_ANCHOR_NAMED = re.compile(r'([\u4e00-\u9fa5A-Za-z0-9]{2,10})锚点')
_UNIT_PEOPLE = re.compile(r'^人物\s*[：:]\s*(.+)')
_ROLE = re.compile(r'@([^\s@、，,｜|（(]+)')
_OTS = re.compile(r'越肩')
_SAME_OK = re.compile(r'同一个人|同一个|只出现一次|不是第二个人|同一位')
_VAGUE = re.compile(r'左边|右边|旁边|对面')
_MIND = re.compile(r'感到|心里|觉得|难过|悲伤|感动|害怕|紧张|开心|痛苦|委屈')

_SPLIT = re.compile(r'[、，,｜|]+')


def roles_of(seg):
    out = []
    for raw in _SPLIT.split(seg or ''):
        t = re.sub(r'[（(].*$', '', raw).strip()
        m = _ROLE.search(t)
        if m:
            out.append(m.group(1))
    return out


def parse(text):
    lines = text.splitlines()
    units, cur = [], None
    for i, raw in enumerate(lines):
        m = _UNIT.match(raw)
        if m:
            cur = {'no': int(m.group(1)), 'lineno': i + 1, 'people': [],
                   'anchors': set(), 'shots': []}
            units.append(cur)
            continue
        if cur is None:
            cur = {'no': 1, 'lineno': 1, 'people': [], 'anchors': set(), 'shots': []}
            units.append(cur)

        mp = _UNIT_PEOPLE.match(raw)
        if mp:
            cur['people'] = roles_of(mp.group(1))
        for a in _ANCHOR_INLINE.findall(raw):
            for nm in re.split(r'[，,、]', a):
                nm = nm.strip()
                if nm:
                    cur['anchors'].add(re.sub(r'(位于|在).*$', '', nm).strip())
        for nm in _ANCHOR_NAMED.findall(raw):
            cur['anchors'].add(nm)

        m = _SHOT.match(raw)
        if m:
            cur['shots'].append({'n': int(m.group(1)), 'lineno': i + 1,
                                 'head': m.group(2).strip(), 'cast': None,
                                 'same': None, 'body': []})
            continue
        if cur['shots']:
            sh = cur['shots'][-1]
            sh['body'].append(raw)
            mc = _CAST.search(raw)
            if mc:
                sh['cast'] = roles_of(mc.group(1))
            ms = _SAME.search(raw)
            if ms:
                sh['same'] = ms.group(1).strip()
    return units


def check(units):
    blockers, warnings, info = [], [], []
    if not units:
        warnings.append({'id': 'CNT-05', 'msg': '没有解析到「单元 N」结构'})

    for u in units:
        tag = f'单元 {u["no"]}'
        known = set(u['people'])
        if not known:
            warnings.append({'id': 'CNT-06', 'msg': f'{tag} 没有解析到「人物：」行，无法核对是否造人'})

        for sh in u['shots']:
            body = '\n'.join(sh['body'])
            who = sh['cast']
            if not who:
                blockers.append({'id': 'CNT-05',
                                 'msg': f'{tag} 镜头 {sh["n"]:02d}（第 {sh["lineno"]} 行）没有「出场人物：」'})
            else:
                if len(who) != len(set(who)):
                    dup = sorted({r for r in who if who.count(r) > 1})
                    blockers.append({'id': 'CNT-09',
                                     'msg': f'{tag} 镜头 {sh["n"]:02d} 出场人物里重复列了：{dup}'})
                if known:
                    extra = [r for r in who if r not in known]
                    if extra:
                        blockers.append({'id': 'CNT-06',
                                         'msg': f'{tag} 镜头 {sh["n"]:02d} 出现「人物：」行里没有的角色：{extra}'})

            # 锚点名登记
            for nm in _ANCHOR_NAMED.findall(body):
                if u['anchors'] and nm not in u['anchors']:
                    blockers.append({'id': 'CNT-07',
                                     'msg': f'{tag} 镜头 {sh["n"]:02d} 用到锚点「{nm}」，但它不在本单元的锚点集合里'})

            # 越肩镜必有同人声明
            if _OTS.search(sh['head']) or _OTS.search(body):
                decl = sh['same'] or ''
                if not decl:
                    blockers.append({'id': 'CNT-08',
                                     'msg': f'{tag} 镜头 {sh["n"]:02d} 是越肩镜但没有「同人声明」——'
                                            f'不写声明时，前景的听方会被当成第二个人（实测已发生两次）'})
                elif not _SAME_OK.search(decl):
                    blockers.append({'id': 'CNT-08',
                                     'msg': f'{tag} 镜头 {sh["n"]:02d} 的「同人声明」没有明确'
                                            f'「是同一个人／本镜只出现一次」：{decl[:40]}'})

            # 只提示不阻断
            for m in set(_VAGUE.findall(body)):
                warnings.append({'id': 'W-方位',
                                 'msg': f'{tag} 镜头 {sh["n"]:02d} 出现无参照方位词「{m}」——'
                                        f'规范要求写成"锚点名+画左/画中/画右"'})
            for m in set(_MIND.findall(body)):
                warnings.append({'id': 'W-心理',
                                 'msg': f'{tag} 镜头 {sh["n"]:02d} 出现心理感受「{m}」——'
                                        f'规范要求"看图说话，只写看得见的身体/脸"'})

        info.append(f'{tag}：{len(u["shots"])} 镜｜角色 {sorted(known) or "（未登记）"}｜锚点 {len(u["anchors"])} 个')

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

    r = check(parse(txt))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        s = r['stats']
        print(f'镜头完整性门禁 · 单元 {s["units"]} 个 / 镜头 {s["shots"]} 个')
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
