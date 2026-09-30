#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台词覆盖门禁 · structural_invariant 层（DIA-01 – DIA-05 / AST-02）

判定（可阻断交付）:
  DIA-01  剧本每句台词（去标点后逐字）必须出现在交付正文中，允许被拆到多个分镜后按顺序拼接还原
  DIA-02  被拆开的台词，各段在同一说话人的台词流中必须连续，中间不得夹该说话人的其他台词
  DIA-03  以逗号／破折号结尾的台词段是残句：它的后半句必须真的接上
  DIA-04  同一句台词不得出现在两个不同的 Clip
  DIA-05  台账「落点」列不得为空（提供 --ledger 时校验）
  AST-02  正文台词不得用 `@名字` 指代人物（应写人物名）

标记但不阻断（reviewed_invariant，交审查者判）:
  DIA-06  同一说话人的台词被拆开，两段之间夹了其他角色的台词

不做（craft_default，交创作者）:
  - 情绪、语速、口型、停顿
  - 分镜该多长、该几个
  - 是否把他人动作塞进说话人镜头（SHT-03）

用法:
  python check_dialogue.py --script 剧本.md --delivery 交付物.md [--ledger 台账.md] [--json]
退出码: 0 = 通过；1 = 有阻断项；2 = 用法/读取错误
"""

import argparse
import json
import re
import sys

# ---------- 归一化 ----------
_PUNCT = re.compile(r'[\s，。、！？；：“”"\'‘’（）()\[\]【】…—\-—,.!?;:·|]+')


def norm(s):
    return _PUNCT.sub('', s or '')


# ---------- Clip 边界 ----------
_CLIP = re.compile(r'^#{2,4}\s*Clip\s*0*(\d+)\b', re.IGNORECASE)


def clip_index_at(lines, upto):
    cur = 1
    for i in range(0, min(upto + 1, len(lines))):
        m = _CLIP.match(lines[i])
        if m:
            cur = int(m.group(1))
    return cur


# ---------- 剧本台词 ----------
_STAGE_HINT = re.compile(r'^[\[【（(]')
_SCRIPT_LINE = re.compile(r'^\s*([^\s：:]{1,10})\s*[：:]\s*(.+?)\s*$')
_SHOT_TITLE = re.compile(r'^[（(]?\s*[\d.]+-[\d.]+\s*秒')


def extract_script(text):
    out = []
    for i, raw in enumerate(text.splitlines()):
        if _CLIP.match(raw):
            continue
        m = _SCRIPT_LINE.match(raw)
        if not m:
            continue
        who, line = m.group(1).strip(), m.group(2).strip()
        if _STAGE_HINT.match(line) or _SHOT_TITLE.match(line):
            continue
        if not norm(line):
            continue
        line = line.strip('“”"\'')
        out.append({'line_no': i + 1, 'who': who, 'text': line, 'norm': norm(line)})
    return out


# ---------- 交付物台词（按已知人名定位，不靠动词） ----------
_QUOTE = re.compile(r'[“"「『]([^”"」』]+)[”"」』]')


def known_names(script, text):
    names = {s['who'] for s in script}
    for raw in text.splitlines():
        m = re.match(r'^\s*\|\s*@?([^|\s]{1,14})\s*\|', raw)
        if m and m.group(1) not in ('资产引用',):
            names.add(m.group(1))
    return sorted(names, key=len, reverse=True)


def extract_delivery(text, names):
    lines = text.splitlines()
    out = []
    for i, raw in enumerate(lines):
        # 承接上一单元那行会引用上一段的台词，它不是本单元的交付内容
        if raw.strip().startswith('承接'):
            continue
        for m in _QUOTE.finditer(raw):
            pre = raw[:m.start()]
            who, at = None, False
            for nm in names:
                idx = pre.rfind(nm)
                if idx >= 0:
                    who = nm
                    at = idx > 0 and pre[idx - 1] == '@'
                    break
            out.append({'lineno': i + 1, 'clip': clip_index_at(lines, i),
                        'who': who, 'text': m.group(1), 'at': at,
                        'vo': '画外音' in pre[-10:]})
    out.sort(key=lambda d: d['lineno'])
    return out


# ---------- 主判定 ----------

def check(script_txt, deliv_txt, ledger_txt):
    blockers, warnings, info = [], [], []
    script = extract_script(script_txt)
    delivery = extract_delivery(deliv_txt, known_names(script, deliv_txt))

    unnamed = [d for d in delivery if d['who'] is None]
    for d in unnamed:
        warnings.append({'id': 'DIA-01', 'msg': f'第 {d["lineno"]} 行的台词定位不到说话人（剧本与资产卡里都没有匹配的人名）：「{d["text"][:20]}…」'})
    delivery = [d for d in delivery if d['who']]

    # AST-02
    for d in delivery:
        if d['at']:
            blockers.append({'id': 'AST-02', 'msg': f'Clip {d["clip"]} 第 {d["lineno"]} 行台词用 `@{d["who"]}` 指代人物，正文应写人物名'})

    # DIA-05 台账落点
    if ledger_txt is not None:
        rows, empties = 0, []
        for i, raw in enumerate(ledger_txt.splitlines()):
            if not raw.strip().startswith('|'):
                continue
            cells = [c.strip() for c in raw.strip().strip('|').split('|')]
            if len(cells) < 4 or set(''.join(cells)) <= set('-: '):
                continue
            if cells[0] in ('剧本位置', '剧本行', '位置'):
                continue
            rows += 1
            if cells[3] in ('', '—', '-', '⬜'):
                empties.append((i + 1, cells[0], cells[2][:22]))
        if rows == 0:
            warnings.append({'id': 'DIA-05', 'msg': '台账里没有解析到数据行（表头或格式不对）'})
        for ln, pos, txt in empties:
            blockers.append({'id': 'DIA-05', 'msg': f'台账第 {ln} 行落点为空：{pos} 「{txt}…」'})

    if not script:
        info.append('剧本里没有解析到台词行（约定格式：`名字：台词`）。DIA-01/02/03 未执行。')
    if not delivery:
        info.append('交付物里没有解析到台词（约定：人物名…：\"台词\"，说话人取自剧本或资产卡人名）。')

    # 按说话人建流
    streams = {}
    for d in delivery:
        streams.setdefault(d['who'], []).append(d)

    # DIA-01/02/03/06
    missing = []
    for who in dict.fromkeys(s['who'] for s in script):
        segs = streams.get(who, [])
        joined = ''.join(norm(s['text']) for s in segs)
        cursor = 0
        for s in [x for x in script if x['who'] == who]:
            target = s['norm']
            pos = joined.find(target, cursor)
            if pos < 0:
                kind = '整句缺失' if joined.find(target) < 0 else '顺序错位'
                missing.append({'id': 'DIA-01', 'who': who, 'line_no': s['line_no'],
                                'text': s['text'], 'kind': kind})
                continue
            covered = []
            for idx, seg in enumerate(segs):
                sidx = len(''.join(norm(x['text']) for x in segs[:idx]))
                if sidx >= pos + len(target):
                    break
                if sidx + len(norm(seg['text'])) > pos:
                    covered.append(idx)
            if len(covered) > 1:
                span = list(range(covered[0], covered[-1] + 1))
                if span != covered:
                    blockers.append({'id': 'DIA-02', 'who': who, 'line_no': s['line_no'],
                                     'msg': f'台词「{s["text"][:20]}…」被拆成 {len(covered)} 段，中间夹了该说话人的其他台词'})
                l1, lk = segs[covered[0]]['lineno'], segs[covered[-1]]['lineno']
                between = [d for d in delivery if l1 < d['lineno'] < lk and d['who'] != who]
                clips = sorted({segs[i]['clip'] for i in covered})
                if len(clips) > 1:
                    info.append(f'跨 Clip 接续：{who}「{s["text"][:16]}…」→ Clip {"→".join(map(str, clips))}（请审查者确认紧邻，DIA-06）')
                if between:
                    warnings.append({'id': 'DIA-06',
                                     'msg': f'{who} 的台词「{s["text"][:18]}…」被拆开，两段之间夹了其他角色 '
                                            f'{len(between)} 段台词（第 {l1} 行 → 第 {lk} 行）—— 交审查者判是否合规'})
            cursor = pos + len(target)
    blockers.extend(missing)

    # DIA-03 独立残句检测：交付段以逗号/破折号结尾，且是某句剧本原句的严格前缀，而该句未被完整覆盖
    for who, segs in streams.items():
        joined = ''.join(norm(s['text']) for s in segs)
        for seg in segs:
            tail = seg['text'].rstrip()
            if not re.search(r'[，,、—]$', tail):
                continue
            frag = norm(tail)
            if len(frag) < 3:
                continue
            for s in [x for x in script if x['who'] == who]:
                if s['norm'].startswith(frag) and s['norm'] != frag and s['norm'] not in joined:
                    missed = s['text'][len(tail.rstrip('，,、—')):].lstrip('，,、—')
                    blockers.append({'id': 'DIA-03', 'who': who, 'line_no': s['line_no'],
                                     'msg': f'残句：Clip {seg["clip"]} 第 {seg["lineno"]} 行以「{tail[-6:]}」结尾，'
                                            f'后半句「{missed[:24]}」没有接续（剧本第 {s["line_no"]} 行）'})
                    break

    # DIA-04 跨 Clip 重复
    seen = {}
    for d in delivery:
        k = norm(d['text'])
        if len(k) >= 2:
            seen.setdefault(k, []).append(d)
    for k, ds in seen.items():
        clips = sorted({d['clip'] for d in ds})
        if len(clips) > 1:
            blockers.append({'id': 'DIA-04', 'msg': f'同一句台词出现在多个 Clip（{clips}）：「{ds[0]["text"][:24]}…」'})

    return {'blockers': blockers, 'warnings': warnings, 'info': info,
            'fired': sorted({b['id'] for b in blockers}),
            'stats': {'script_lines': len(script), 'delivery_lines': len(delivery), 'speakers': len(streams)}}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--script', required=True)
    ap.add_argument('--delivery', required=True)
    ap.add_argument('--ledger', default=None)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    try:
        st = open(a.script, encoding='utf-8').read()
        dt = open(a.delivery, encoding='utf-8').read()
        lt = open(a.ledger, encoding='utf-8').read() if a.ledger else None
    except OSError as e:
        print(f'读取失败: {e}', file=sys.stderr)
        return 2

    r = check(st, dt, lt)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        s = r['stats']
        print(f'台词覆盖门禁 · 剧本 {s["script_lines"]} 句 / 交付物 {s["delivery_lines"]} 段 / 说话人 {s["speakers"]}')
        print('-' * 60)
        if r['blockers']:
            print(f'❌ 阻断项 {len(r["blockers"])} 条（不得交付）:')
            for b in r['blockers']:
                print(f'   [{b.get("id")}] {b.get("msg") or (b.get("kind","") + "：" + b.get("who","") + "：" + b.get("text",""))}')
        else:
            print('✅ 无阻断项')
        for w in r['warnings']:
            print(f'⚠️  [{w["id"]}] {w["msg"]}')
        for m in r['info']:
            print(f'ℹ️  {m}')
    return 1 if r['blockers'] else 0


if __name__ == '__main__':
    sys.exit(main())
