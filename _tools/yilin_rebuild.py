# -*- coding: utf-8 -*-
"""易林4096签卦变映射重建 v4。
体例：64节×64条，节内=本卦之X："本卦之本项目"置顶+其余63条按文王序（SEQ模型）。
状态：p=下一个待填slot；接受条目时p+1。p满64遇头=换节。
失配恢复：a)节内前跳（中间缺）b)下一节开头（本节尾缺+下节首缺）。全部损伤如实报告。"""
import re, json, sys

SRC = '_sources/siku_fulltext/daizhige/焦氏易林.txt'
OUT = 'skill-coin-knows/assets/yilin_hexagrams.json'
ALIAS = {'旡妄': '无妄', '遯': '遁'}

raw = open(SRC, encoding='utf-8', errors='replace').read()
lines = [l.rstrip() for l in raw.split('\n')]
lines = [l for l in lines if l.strip() and not l.startswith('■■■') and l.strip() != '.']

front = raw[:raw.find('■■■此起为蛊卦■■■')]
KINGWEN = []
for x, y in re.findall(r'(?m)^([^\u3000\n之]{1,2})之([^\u3000\n之]{1,3})$', front):
    if x == '乾' and y not in KINGWEN:
        KINGWEN.append(y)
assert len(KINGWEN) == 64 and KINGWEN[0] == '乾' and KINGWEN[-1] == '未济'
IDX = set(KINGWEN)

def norm(n):
    n = n.replace(' ', '').replace('-', '').replace('\u3000', '')
    return ALIAS.get(n, n)

SEQ = [ [KINGWEN[k]] + [n for i, n in enumerate(KINGWEN) if i != k] for k in range(64) ]

def head_of(line):
    m = re.match(r'^([^\u3000\n之]{1,2})之([^\u3000\n之]{1,3})$', line)
    if m:
        x, y = norm(m.group(1)), norm(m.group(2))
        if x in IDX and y in IDX:
            return ('full', x, y, '')
    m = re.match(r'^\u3000?([^\u3000\n\s之]{1,3})\u3000+(\S.*)$', line)
    if m:
        y = norm(m.group(1))
        if y in IDX:
            return ('short', None, y, m.group(2))
    return None

entries, damage, notes = [], [], []
k, p = 0, 0
cur_to, pending = None, []

def close_open():
    global cur_to, pending
    if cur_to is not None:
        entries.append((KINGWEN[k], cur_to, ''.join(pending).strip() or None))
    cur_to, pending = None, []

def accept(y, rest, is_short):
    global cur_to, pending
    cur_to, pending = y, ([rest] if is_short else [])

for ln in lines:
    h = head_of(ln)
    if not h:
        if cur_to is not None:
            pending.append(ln)
        continue
    _, x, y, rest = h
    is_short = h[0] == 'short'
    if p >= 64:                                   # 换节
        close_open()
        k += 1
        p = 0
    if x is not None and x != KINGWEN[k]:
        notes.append(f'[{k+1:02d}·{KINGWEN[k]}] 全名头本卦{x}≠{KINGWEN[k]}：{ln[:18]}')
    seq = SEQ[k]
    if p < 64 and y == seq[p]:                    # 正中
        close_open()
        accept(y, rest, is_short)
        p += 1
    elif p < 64 and y in seq[p+1:]:               # 节内前跳：中间slot缺
        q = seq.index(y)
        close_open()
        for miss in range(p, q):
            entries.append((KINGWEN[k], seq[miss], None))
            damage.append(f'{KINGWEN[k]}之{seq[miss]}')
        accept(y, rest, is_short)
        p = q + 1
    elif p < 64 and k < 63 and y in SEQ[k+1]:     # 下一节开头：本节尾缺+下节首(们)缺
        q = SEQ[k+1].index(y)
        close_open()
        for miss in range(p, 64):
            entries.append((KINGWEN[k], seq[miss], None))
            damage.append(f'{KINGWEN[k]}之{seq[miss]}(节尾缺)')
        k += 1
        for miss in range(0, q):
            entries.append((KINGWEN[k], SEQ[k][miss], None))
            damage.append(f'{KINGWEN[k]}之{SEQ[k][miss]}(节首缺)')
        accept(y, rest, is_short)
        p = q + 1
    else:
        notes.append(f'[{k+1:02d}·{KINGWEN[k]}] 位{p+1}期望{seq[p] if p<64 else "满"}遇{y}，无法安置：{ln[:18]}')
close_open()

print(f'总slot: {len(entries)}（应4096）；实收繇辞: {sum(1 for e in entries if e[2])}；缺口: {len(damage)}')
for d in damage[:12]:
    print('  缺:', d)
print(f'notes: {len(notes)}')
for n in notes[:12]:
    print('  note:', n)
by_sec = {}
for f_, t_, tx in entries:
    by_sec.setdefault(f_, []).append(t_)
sec_bad = [(s, len(ts)) for s, ts in by_sec.items() if ts != SEQ[KINGWEN.index(s)]]
print('异常节:', sec_bad[:8], f'共{len(sec_bad)}')

if len(entries) == 4096 and not sec_bad and not notes:
    missing = [f'{f_}之{t_}' for f_, t_, tx in entries if tx is None]
    out = {
        'meta': {
            'name': '焦氏易林4096签·卦变映射表',
            'structure': 'from(本卦,文王序)/to(之卦,文王序)/text(繇辞)；text=null=殆知阁源即缺（slot保留）',
            'source': '殆知阁·焦氏易林.txt（电子重排版，内容级；校勘引证以四库本为准）',
            'rebuild': '2026-10-11 批74：序位锚定状态机重建（节内=本卦之本项目置顶+其余按文王序），全4096slot序列校验通过',
            'missing_count': len(missing),
            'missing': missing,
            'usage': '真算引擎专用：梅花起卦得本卦+动爻→变卦→查 from==本卦&&to==变卦；slot缺则顺延至同本卦下一有签之位（确定性规则）',
        },
        'kingwen': KINGWEN,
        'signs': [{'from': f_, 'to': t_, 'text': tx} for f_, t_, tx in entries],
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('落盘:', OUT, '缺签', len(missing), '条')
    for i in (0, 1, 2048, 4095):
        e = entries[i]
        print('抽样:', e[0], '之', e[1], (e[2] or '(缺)')[:24])
else:
    print('!! 校验未过，不落盘')
    sys.exit(1)
