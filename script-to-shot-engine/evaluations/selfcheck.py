#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能自查 —— 检查这套东西自己有没有互相矛盾。

它不管内容写得好不好，只管**一致性**：

  SC-01  版本号四处一致（VERSION / SKILL.md 第 6 行 / 两个 README 的徽章与页脚）
  SC-02  markdown 相对链接没有死链
  SC-03  脚本里 fire 的规则 ID 都在 rule-tiers.md 登记过
  SC-04  rule-tiers.md 里标为「脚本可阻断」的 ID 都有脚本在 fire
  SC-05  gate.py 覆盖 scripts/ 下所有 check_*.py
  SC-06  每个夹具都有 expected.json，且其 must_fire 的 ID 都已登记
  SC-07  没有过时措辞残留（「空间站位」「焦距/85mm」不该出现在新主干与 SKILL.md）
  SC-08  编码无替换字符（U+FFFD）、无 BOM
  SC-09  本机安装版与源码逐文件一致（安装版不存在时跳过）

用法:
  python selfcheck.py [--json]
退出码: 0 = 全过；1 = 有不一致；2 = 环境错误
"""

import argparse
import json
import os
import re
import sys


# Windows 控制台默认 GBK：✅/❌ 会抛 UnicodeEncodeError，把门禁直接打崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INSTALLED = os.path.join(os.path.expanduser('~'), '.dsh', 'skills', 'script-to-shot-engine')

_U8 = 'utf-8'
RESULT = []


def rec(code, ok, msg):
    RESULT.append({'id': code, 'ok': bool(ok), 'msg': msg})
    return ok


def read(p):
    with open(p, encoding=_U8) as fh:
        return fh.read()


def md_files():
    out = []
    for base in (ROOT, os.path.join(ROOT, 'references'), os.path.join(ROOT, 'evaluations'),
                 os.path.join(ROOT, 'templates')):
        if not os.path.isdir(base):
            continue
        for dirpath, _d, files in os.walk(base):
            if os.sep + '.git' in dirpath:
                continue
            for f in files:
                if f.endswith('.md'):
                    out.append(os.path.join(dirpath, f))
    return out


# ---- SC-01 版本一致 ----
def sc01():
    ver = read(os.path.join(ROOT, 'VERSION')).strip()
    bad = []
    skill_line = read(os.path.join(ROOT, 'SKILL.md')).splitlines()[5]
    if ver not in skill_line:
        bad.append(f'SKILL.md 第6行：「{skill_line}」')
    for f in ('README.md', 'README.zh-CN.md'):
        t = read(os.path.join(ROOT, f))
        if f'version-{ver}-' not in t:
            bad.append(f'{f} 徽章')
        if f'v{ver}<' not in t:
            bad.append(f'{f} 页脚')
    return rec('SC-01', not bad, f'版本 {ver} 四处一致' if not bad else ' | '.join(bad))


# ---- SC-02 死链 ----
_LINK = re.compile(r'\]\(([^)#\s]+\.md)\)')


def sc02():
    bad = []
    for p in md_files():
        for target in _LINK.findall(read(p)):
            if target.startswith(('http://', 'https://')):
                continue
            t = os.path.normpath(os.path.join(os.path.dirname(p), target))
            if not os.path.isfile(t):
                bad.append(f'{os.path.relpath(p, ROOT)} → {target}')
    return rec('SC-02', not bad, f'{len(md_files())} 个 md，无死链' if not bad else ' | '.join(bad[:6]))


# ---- ID 集合 ----
def registered_ids():
    t = read(os.path.join(ROOT, 'references', 'rule-tiers.md'))
    return set(re.findall(r'`([A-Z]{2,4}-\d{2})`', t))


def script_fired_ids():
    got = {}
    sd = os.path.join(ROOT, 'scripts')
    for f in sorted(os.listdir(sd)):
        if not f.startswith('check_') or not f.endswith('.py'):
            continue
        ids = set(re.findall(r"'id':\s*'([A-Z]{2,4}-\d{2})'", read(os.path.join(sd, f))))
        ids |= set(re.findall(r'\{"id":\s*"([A-Z]{2,4}-\d{2})"', read(os.path.join(sd, f))))
        got[f] = ids
    return got


def sc03():
    reg = registered_ids()
    fired = set()
    for v in script_fired_ids().values():
        fired |= v
    unreg = sorted(fired - reg)
    return rec('SC-03', not unreg,
               f'脚本 fire 的 {len(fired)} 个 ID 全部已登记' if not unreg
               else f'未登记的 ID：{unreg}')


def sc04():
    """rule-tiers 里写「校验器可阻断」的 ID 应该有脚本在 fire。标了「待实现」的不算。"""
    t = read(os.path.join(ROOT, 'references', 'rule-tiers.md'))
    head = t.split('## reviewed_invariant')[0]
    claimed = set()
    for line in head.splitlines():
        if '待实现' in line:
            continue
        claimed |= set(re.findall(r'\| `([A-Z]{2,4}-\d{2})`', line))
    fired = set()
    for v in script_fired_ids().values():
        fired |= v
    missing = sorted(claimed - fired)
    return rec('SC-04', not missing,
               f'structural 表里 {len(claimed)} 个 ID 都有脚本' if not missing
               else f'标了脚本可阻断但没有脚本：{missing}')


def sc05():
    names = [f for f in os.listdir(os.path.join(ROOT, 'scripts'))
             if f.startswith('check_') and f.endswith('.py')]
    g = read(os.path.join(ROOT, 'evaluations', 'gate.py'))
    missing = [n for n in names if f"'{n}'" not in g]
    return rec('SC-05', not missing,
               f'gate.py 覆盖全部 {len(names)} 个检查脚本' if not missing
               else f'gate.py 未覆盖：{missing}')


def sc06():
    reg = registered_ids()
    cases = os.path.join(ROOT, 'evaluations', 'cases')
    bad = []
    if not os.path.isdir(cases):
        return rec('SC-06', False, '缺 cases 目录')
    names = sorted(d for d in os.listdir(cases) if os.path.isdir(os.path.join(cases, d)))
    for n in names:
        p = os.path.join(cases, n, 'expected.json')
        if not os.path.isfile(p):
            bad.append(f'{n} 缺 expected.json')
            continue
        exp = json.loads(read(p))
        for _script, ids in (exp.get('must_fire') or {}).items():
            for i in ids:
                if i not in reg:
                    bad.append(f'{n} must_fire 里的 {i} 未登记')
        if not os.path.isfile(os.path.join(cases, n, 'delivery.md')):
            bad.append(f'{n} 缺 delivery.md')
    return rec('SC-06', not bad,
               f'{len(names)} 个夹具，expected/must_fire 全部自洽' if not bad else ' | '.join(bad[:6]))


_HISTORY = ('实测', '不再写', '已废弃', '旧格式', '迁移', '为什么', '教训', '旧写法', '不加', '不要')


def sc07():
    """过时措辞：全技能不该再有这些。讲历史/讲教训的行除外。"""
    # 规范文件全集（不含 examples／cases：那是历史产物，另有「不要照抄」警告）
    SPEC = ['SKILL.md', 'references/group-format.md', 'references/constraints.md',
            'references/setup.md', 'references/space.md', 'references/timing.md',
            'references/shots.md', 'references/dialogue.md', 'references/output.md',
            'references/gates.md', 'references/troubleshooting.md',
            'references/dialogue-scene-mode.md', 'references/continuous-mode.md',
            'references/action-choreography-rules.md', 'references/rule-tiers.md',
            'references/pre-shot-checklist.md', 'references/asset-anchor-protocol.md',
            'templates/project/01-档案/项目档案.md']
    stale = {
        'anchor': (SPEC, [r'空间站位', r'在场人物']),
        'focal': (SPEC, [r'85mm', r'135mm', r'焦段']),
        'density': (SPEC, [r'信息密度配额']),
        # 台词字数不单列（字数只出现在「时长计算」的算式里）
        'charfield': (SPEC, [r'台词字数约']),
        # 旧的加数名（现统一叫「表演与停顿」）
        'oldadd': (['SKILL.md', 'references/timing.md', 'references/dialogue.md',
                    'references/dialogue-scene-mode.md',
                    'templates/project/01-档案/项目档案.md'], [r'口型缓冲', r'情绪停顿']),
        'old_shot': (['references/timing.md'], [r'^分镜\d+（']),
        # 「一轮只出一个单元」已废弃：它让"先分镜后装箱"根本没法发生
        'one_unit': (['SKILL.md', 'references/timing.md'],
                     [r'只输出 1 个单元', r'一次只输出', r'下一单元从', r'→ 第一个单元']),
        # 旧格式残留：台账/接续必须用「单元」，不能再出现 Clip
        'clip_ref': (['SKILL.md', 'references/timing.md'],
                     [r'Clip ?\d+ ?镜头', r'跨 Clip']),
        # 语速只许有一套数字。旧表（3／4／5.5）不许回到规范文件里
        'rate2': (['SKILL.md', 'references/timing.md', 'references/dialogue.md',
                    'references/dialogue-scene-mode.md',
                   'references/rule-tiers.md', 'templates/project/01-档案/项目档案.md'],
                  [r'≈\s*3\s*字/秒', r'≈\s*4\s*字/秒', r'≈\s*5—5\.5', r'4—5\s*字/秒', r'5—5\.5\s*字/秒']),
    }
    hits = []
    for _key, (files, pats) in stale.items():
        for f in files:
            for ln, line in enumerate(read(os.path.join(ROOT, f)).splitlines(), 1):
                if any(k in line for k in _HISTORY):
                    continue
                for p in pats:
                    if re.search(p, line):
                        hits.append(f'{f}:{ln} 「{p}」→ {line.strip()[:36]}')
    return rec('SC-07', not hits, '新主干与 SKILL.md 无过时措辞' if not hits else ' | '.join(hits[:6]))


def sc08():
    bad = []
    n = 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', '.push-deepseek')]
        for f in files:
            if not f.endswith(('.md', '.py', '.json', '.yaml')):
                continue
            p = os.path.join(dirpath, f)
            n += 1
            raw = open(p, 'rb').read()
            if raw.startswith(b'\xef\xbb\xbf'):
                bad.append(f'{f} 有 BOM')
            if '\ufffd' in raw.decode(_U8, errors='replace'):
                bad.append(f'{f} 有替换字符')
    return rec('SC-08', not bad, f'{n} 个文本文件编码干净' if not bad else ' | '.join(bad[:6]))


def sc09():
    if not os.path.isdir(INSTALLED):
        return rec('SC-09', True, '未发现本机安装版，跳过')
    src, bad, missing = [], [], 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', '.push-deepseek')]
        for f in files:
            if f == '.last-run.txt':
                continue
            p = os.path.join(dirpath, f)
            src.append(os.path.relpath(p, ROOT))
    for rel in src:
        d = os.path.join(INSTALLED, rel)
        if not os.path.isfile(d):
            missing += 1
            continue
        if open(os.path.join(ROOT, rel), 'rb').read() != open(d, 'rb').read():
            bad.append(rel)
    ok = (missing == 0 and not bad)
    return rec('SC-09', ok,
               f'安装版与源码一致（{len(src)} 文件）' if ok
               else f'不一致 {len(bad)}｜缺失 {missing}：{(bad[:4] or [])}')


def sc10():
    """每个脚本都要有 UTF-8 兜底。

    Windows 控制台默认 GBK，脚本里的 ✅/❌ 会抛 UnicodeEncodeError **把门禁直接打崩**。
    之前一直没暴露，是因为运行时手动设了 PYTHONIOENCODING=utf-8——
    「在某个人的机器上能跑」不等于「能跑」。
    """
    bad = []
    for d in ('scripts', 'evaluations'):
        p = os.path.join(ROOT, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            if not f.endswith('.py'):
                continue
            t = read(os.path.join(p, f)).replace('"', "'")
            if "reconfigure(encoding='utf-8'" not in t:
                bad.append(f'{d}/{f}')
    return rec('SC-10', not bad,
               '所有脚本都有 UTF-8 兜底（Windows GBK 控制台不会崩）' if not bad
               else f'缺 UTF-8 兜底：{bad}')


def sc11():
    """规则 ID 不得重复定义。

    教训：加 `FMT-02`（缺单元标题）时没先查表——而 `FMT-02` 早已被「台账排版」占用。
    **同一个 ID 两个含义，比没有 ID 更糟**：引用它的人不知道该按哪条执行。
    """
    t = read(os.path.join(ROOT, 'references', 'rule-tiers.md'))
    seen, dup = {}, []
    # 只认「定义行」：ID 必须落在该行的**第一个单元格**。
    # 引用行（脚本覆盖表、降级记录）本来就会重复提到 ID，不算撞号。
    for ln, line in enumerate(t.splitlines(), 1):
        m = re.match(r'\|\s*`([A-Z]{2,4}-\d{2})`\s*\|', line)
        if not m:
            continue
        vid = m.group(1)
        if vid in seen:
            dup.append(f'{vid}（第 {seen[vid]} 行 与 第 {ln} 行）')
        else:
            seen[vid] = ln
    return rec('SC-11', not dup,
               f'{len(seen)} 个规则 ID 无重复定义' if not dup else f'ID 撞号：{dup}')


def sc12():
    """模板里不该再出现被禁的节奏写法。

    教训：`DIA-15` 说"永不写字字清晰"，而 §6.1 的台词句式表里**每一行都带着它**——
    改了规则没扫载体，模型照模板写，规则等于没改。
    """
    files = ('SKILL.md', 'references/timing.md', 'references/dialogue-scene-mode.md',
             'references/pre-shot-checklist.md', 'templates/project/01-档案/项目档案.md')
    okmark = ('不要', '永不', '禁止', '✗', '教训')
    hit = []
    for f in files:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        for ln, line in enumerate(read(p).splitlines(), 1):
            # 出现在「」里的算**引用**（解释为什么禁），不算教写；模板是把它们裸写的
            bare = re.sub(r'「[^」]*」', '', line)
            for bad in ('字字清晰', '语速缓慢'):
                if bad in bare and not any(k in line for k in okmark):
                    hit.append(f'{f}:{ln} 「{bad}」')
    return rec('SC-12', not hit,
               '模板里没有残留被禁的节奏写法' if not hit else f'仍在教写：{hit[:6]}')


REQUIRED_FIELDS = ('场景', '出场人物', '空间坐标', '同人声明', '画面描述',
                   '光影', '运镜', '构图', '声画同步', '台词同期', '台词', '停顿',
                   '台词节奏', '本镜禁止', '强制约束')


def sc13():
    """SKILL.md 必须**只指向** §9 模板，不得重述逐镜字段。

    老版本的 SC-13 是"两处字段表必须一致"——那是在给**重复**做守卫。
    拆开之后正确的纪律是**没有重复**：逐镜字段只有一个家（`output.md` §9）。
    **少一处重述，就少一处打架。**
    """
    skill = read(os.path.join(ROOT, 'SKILL.md'))
    m = re.search(r'逐镜写[^\n]*', skill)
    if not m:
        return rec('SC-13', False, '定位不到 SKILL.md 的「逐镜写」指引')
    line = m.group(0)
    # 「重述字段表」= 列了一**串**字段。只提一两个词（例如标题格式里的 `运镜方式`）不算。
    dup = [f for f in REQUIRED_FIELDS if f in line]
    if len(dup) >= 4:
        return rec('SC-13', False,
                   f'SKILL.md 又重述了逐镜字段 {dup[:6]}（共 {len(dup)} 个）——'
                   f'应只指向 output.md §9，字段只有一个家')
    ok = 'output.md' in line and '不重述' in line
    return rec('SC-13', ok,
               'SKILL.md 只指向 output.md §9，不重述逐镜字段' if ok
               else '「逐镜写」没有指向 output.md §9')


# 配额行的解析：`15 秒：… 5—8 镜，单镜 2—4 秒` / `30 秒 … 10—18 镜`
_QUOTA = re.compile(r'(?P<cap>\d+)\s*秒[^。；\n]*?(?P<lo>\d+)\s*[—－~-]\s*(?P<hi>\d+)\s*镜(?P<rest>[^。；\n]*)')
_SHOTLEN = re.compile(r'单镜\s*(?P<flo>\d+(?:\.\d+)?)\s*[—－~-]\s*(?P<fhi>\d+(?:\.\d+)?)\s*秒')

# 没有写单镜时长时的隐含下限：一拍少于 1 秒就不是镜头，是闪帧
DEFAULT_MIN_SHOT = 1.0


def sc14():
    """数值配额必须**算术上可能**。

    教训：`15 秒：5—8 镜，单镜 2—4 秒` —— 8×2=16s、5×4=20s，两条都超过 15 秒上限。
    这种冲突靠读是看不出来的，必须算。判据：**镜数上限 × 单镜下限 ≤ 单元上限**，
    否则"镜数上限"永远达不到（写成配额就是骗人）。
    """
    files = ['SKILL.md', 'references/dialogue-scene-mode.md',
             'references/action-choreography-rules.md', 'references/continuous-mode.md',
             'references/timing.md']
    bad, seen = [], []
    for f in files:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        for ln, line in enumerate(read(p).splitlines(), 1):
            for m in _QUOTA.finditer(line):
                cap = float(m.group('cap'))
                hi = float(m.group('hi'))
                sl = _SHOTLEN.search(m.group('rest'))
                floor = float(sl.group('flo')) if sl else DEFAULT_MIN_SHOT
                need = round(hi * floor, 2)
                seen.append(f"{f}:{ln} {m.group(0).strip()[:44]}")
                if need > cap + 1e-6:
                    bad.append(f'{f}:{ln} 「{m.group(0).strip()[:40]}」→ {hi:g}镜 × {floor:g}秒 = '
                               f'{need:g}s > {cap:g}s 上限，镜数上限达不到')
    return rec('SC-14', not bad,
               f'{len(seen)} 条数值配额，算术上都成立' if not bad else ' | '.join(bad[:4]))


def sc15():
    """SKILL.md 的文件地图必须索引 references/ 下每一个 .md，且不链到不存在的文件。

    教训：所有主题塞在一个文件里时，"改了 A 节、B 节还留着旧说法"没人能发现。
    拆开之后，**"有没有被索引"就变成了机器可查的事**。
    """
    skill = read(os.path.join(ROOT, 'SKILL.md'))
    refdir = os.path.join(ROOT, 'references')
    have = {f for f in os.listdir(refdir) if f.endswith('.md')}
    linked = set(re.findall(r'\]\(references/([^)]+\.md)\)', skill))
    dead = sorted(x for x in linked if x not in have)
    missing = sorted(have - linked)
    if dead:
        return rec('SC-15', False, f'SKILL.md 链到不存在的文件：{dead}')
    return rec('SC-15', not missing,
               f'SKILL.md 索引了全部 {len(have)} 个 references 文件' if not missing
               else f'没被 SKILL.md 索引：{missing}')


def sc16():
    """正文里引用的 §N，必须有对应的 `# §N` 标题。

    教训：我们特意**保留 `# §N` 编号不做重排**——因为正文里有大量「见 §5.1」。
    重排编号 = 全部指空。这条守卫让"指空"当场变红。
    """
    text = ''
    for d in ('', 'references', 'templates', 'evaluations'):
        base = os.path.join(ROOT, d) if d else ROOT
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            if f.endswith('.md'):
                text += read(os.path.join(base, f)) + '\n'
    defined = set(re.findall(r'(?m)^#\s*§(\d+)', text))
    defined |= {m.split('.')[0] for m in re.findall(r'(?m)^##\s*(\d+\.\d+)', text)}
    mentioned = set(re.findall(r'§(\d+)', text))
    undef = sorted(mentioned - defined, key=lambda x: int(x))
    return rec('SC-16', not undef,
               f'{len(mentioned)} 个 §N 引用全部有对应章节' if not undef
               else f'引用指空：{["§" + x for x in undef]}')


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    for fn in (sc01, sc02, sc03, sc04, sc05, sc06, sc07, sc08, sc09, sc10, sc11, sc12,
               sc13, sc14, sc15, sc16):
        try:
            fn()
        except Exception as e:  # 自查本身出错也要报出来
            rec(fn.__name__.upper(), False, f'自查项异常：{e}')

    fails = [r for r in RESULT if not r['ok']]
    if a.json:
        print(json.dumps({'results': RESULT, 'failed': len(fails)}, ensure_ascii=False, indent=2))
    else:
        print('技能自查')
        print('-' * 64)
        for r in RESULT:
            print(f'  {"✅" if r["ok"] else "❌"} [{r["id"]}] {r["msg"]}')
        print('-' * 64)
        print(f'{"全部通过" if not fails else str(len(fails)) + " 项不一致"}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
