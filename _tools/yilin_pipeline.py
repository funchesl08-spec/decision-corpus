# -*- coding: utf-8 -*-
"""易林4096签卦变映射重建 v5 最终管线。
步骤：①序位锚定解析（半角空白容错+裸名行=节界标志）②断头抢救 ③旧库(yilin_qian)对照清洗文本
④空位从旧库回填 ⑤全量校验（64节×64条序列）→落盘。
全部决策打印留痕；校验不过不落盘。"""
import re, json, sys

SRC = '_sources/siku_fulltext/daizhige/焦氏易林.txt'
OUT = 'skill-coin-knows/assets/yilin_hexagrams.json'
OLD = 'skill-coin-knows/assets/yilin_qian.json'
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

SEQ = [[KINGWEN[k]] + [n for i, n in enumerate(KINGWEN) if i != k] for k in range(64)]

def head_of(line):
    m = re.match(r'^\s*\u3000*([^\u3000\n\s之]{1,3})\u3000+(\S.*)$', line)
    if m:
        y = norm(m.group(1))
        if y in IDX:
            return ('short', None, y, m.group(2))
    m = re.match(r'^([^\u3000\n之]{1,2})之([^\u3000\n之]{1,3})$', line)
    if m:
        x, y = norm(m.group(1)), norm(m.group(2))
        if x in IDX and y in IDX:
            return ('full', x, y, '')
    return None

def bare_of(line):
    m = re.match(r'^\s*\u3000*([^\u3000\n\s之]{1,3})\u3000*$', line)
    if m:
        y = norm(m.group(1))
        if y in IDX:
            return y
    return None

entries, damage, notes, marks_used = [], [], [], 0
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
    bare = bare_of(ln)
    if bare is not None:
        close_open()
        if bare == KINGWEN[k + 1] if k < 63 else False:
            if p < 64:
                for miss in range(p, 64):
                    entries.append((KINGWEN[k], SEQ[k][miss], None))
                    damage.append(f'{KINGWEN[k]}之{SEQ[k][miss]}(节尾缺@裸界)')
            k += 1
            p = 0
            marks_used += 1
            continue
        else:
            notes.append(f'裸名行{bare}≠下一节{KINGWEN[k+1] if k<63 else "-"}（当前{k+1:02d}·{KINGWEN[k]}位{p+1}），跳过')
            continue
    h = head_of(ln)
    if not h:
        if cur_to is not None:
            pending.append(ln)
        continue
    _, x, y, rest = h
    is_short = h[0] == 'short'
    if p >= 64:
        close_open()
        k += 1
        p = 0
    if x is not None and x != KINGWEN[k]:
        notes.append(f'[{k+1:02d}·{KINGWEN[k]}] 全名头{x}≠{KINGWEN[k]}：{ln[:18]}')
    seq = SEQ[k]
    if p < 64 and y == seq[p]:
        close_open()
        accept(y, rest, is_short)
        p += 1
    elif p < 64 and y in seq[p+1:]:
        q = seq.index(y)
        close_open()
        for miss in range(p, q):
            entries.append((KINGWEN[k], seq[miss], None))
            damage.append(f'{KINGWEN[k]}之{seq[miss]}')
        accept(y, rest, is_short)
        p = q + 1
    elif p < 64 and k < 63 and y in SEQ[k+1]:
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
        notes.append(f'[{k+1:02d}·{KINGWEN[k]}] 位{p+1}期望{seq[p] if p<64 else "满"}遇{y}：{ln[:18]}')
close_open()

print(f'①解析：slot {len(entries)}/4096，裸名节界用 {marks_used} 次')
by_sec = {}
for f_, t_, tx in entries:
    by_sec.setdefault(f_, []).append(t_)
sec_bad = [(s, len(ts)) for s, ts in by_sec.items() if ts != SEQ[KINGWEN.index(s)]]
print('   序列异常节:', sec_bad[:6], f'共{len(sec_bad)}；notes {len(notes)}')
for n in notes[:8]:
    print('   note:', n)

# ②断头抢救
salv = 0
salv_log = []
for i, e in enumerate(entries):
    if e[2] is not None or i == 0:
        continue
    X, Y = e[0], e[1]
    prev = entries[i-1]
    if prev[2] is None:
        continue
    cands = []
    for m in re.finditer(r'(?:^|。)%s之([^\u3000，。；！？\n]{1,3})' % re.escape(X), prev[2]):
        frag = m.group(1)
        if Y.startswith(frag):
            verse = prev[2][m.end():]
            if 10 <= len(verse) <= 150 and '。' in verse:
                cands.append((m.start(), m.end(), verse))
    for m in re.finditer(r'(?:^|。)\u3000?([^\u3000，。；！？\n]{1,3})\u3000+', prev[2]):
        if Y.startswith(m.group(1)):
            verse = prev[2][m.end():]
            if 10 <= len(verse) <= 150 and '。' in verse:
                cands.append((m.start(), m.end(), verse))
    if len(cands) == 1:
        s0, e0, verse = cands[0]
        keep_period = prev[2][s0] == '。'
        prev_head = list(prev)
        prev_head[2] = (prev[2][:s0] + ('。' if keep_period else '')) or None
        entries[i-1] = tuple(prev_head)
        entries[i] = (X, Y, verse.strip())
        salv += 1
        salv_log.append(f'{X}之{Y} ← 前条切分')
print(f'②抢救：还原 {salv} 条')
for s in salv_log:
    print('   ', s)

# ③旧库对照清洗
old = json.load(open(OLD, encoding='utf-8'))
old_texts = set(s['text'] for s in old['signs'])
cleaned, unmatched = 0, []
def clean_variants(t):
    outs = {t}
    a = re.sub(r'（[^（）]*）\s*$', '', t)
    if a != t:
        outs.add(a.rstrip('，；'))
    b = re.sub(r'[（(][^（）()]*之[^（）()]*[）)]\s*$', '', t)
    if b != t:
        outs.add(b)
    c = re.sub(r'[）)]\s*$', '', t)
    outs.add(c)
    d = re.sub(r'。\s*[^\u3000，。；！？\n]{1,3}之[^\u3000，。；！？\n]{1,3}[）)]\s*$', '。', t)
    outs.add(d)
    return outs
for i, e in enumerate(entries):
    if e[2] is None or e[2] in old_texts:
        continue
    hit = None
    for cand in clean_variants(e[2]):
        if cand in old_texts:
            hit = cand
            break
    if hit is None:
        pref = re.sub(r'（[^（）]*）', '', e[2])[:12]
        cands = [t for t in old_texts if t.startswith(pref)]
        if len(cands) == 1:
            hit = cands[0]
    if hit is not None:
        entries[i] = (e[0], e[1], hit)
        cleaned += 1
    else:
        unmatched.append((e[0], e[1], e[2][-30:]))
print(f'③旧库清洗：对齐 {cleaned} 条；未对齐 {len(unmatched)}')
for u in unmatched[:10]:
    print('   未对齐:', u)

# ④空位回填（只收干净候选：不以标点起头、不以）收尾、长度合理）
def is_clean(t):
    return bool(t) and 10 <= len(t) <= 160 and not re.match(r'^[，。；！？、）\s]', t) and not re.search(r'[）)]\s*$', t)

used = set(e[2] for e in entries if e[2])
filled = 0
fill_log = []
for i, e in enumerate(entries):
    if e[2] is not None:
        continue
    X, Y = e[0], e[1]
    cands = [s['text'] for s in old['signs'] if s.get('to') == Y and s['text'] not in used and is_clean(s['text'])]
    if len(cands) > 1:
        cands2 = [s['text'] for s in old['signs'] if s.get('from') == X and s.get('to') == Y and s['text'] not in used and is_clean(s['text'])]
        cands = cands2 if len(cands2) == 1 else cands
    if len(cands) == 1:
        entries[i] = (X, Y, cands[0])
        used.add(cands[0])
        filled += 1
        fill_log.append(f'{X}之{Y} ← 旧库回填: {cands[0][:20]}…')
print(f'④旧库回填：{filled} 条')
for s in fill_log:
    print('   ', s)
still_null = sum(1 for e in entries if e[2] is None)
print(f'   终态空位: {still_null}')
for e in entries:
    if e[2] is None:
        print('   null:', e[0], '之', e[1])

# ⑤终检+落盘
final = []
for f_, t_, tx in entries:
    if tx is not None:
        tx = tx.strip().strip('\u3000').strip()
        # 尾部互见垃圾截断：末句号之后若含'）'或纯卦名链，截到末句号
        m = re.search(r'^(.*。)[^。]*[）)]$', tx)
        if m and ('之' in tx[m.end(1):] or re.search(r'[乾坤屯蒙需讼师比小畜履泰否同人大有谦豫随蛊临观噬嗑贲剥复无妄大畜颐大过坎离咸恒遯遁大壮晋明夷家人睽蹇解损益夬姤萃升困井革鼎震艮渐归妹丰旅巽兑涣节中孚小过既济未济]{2,}[）)]$', tx[m.end(1):])):
            tx = m.group(1)
    final.append((f_, t_, tx))
entries = final
resid = []
for e in entries:
    if e[2] and re.search(r'[）)]\s*$', e[2]):
        resid.append((e[0], e[1], e[2][-24:]))
print('残留）尾:', len(resid), resid[:6])
# 首节对照：乾之X 与旧库逐条比对（旧库前18节from可靠）
qian_old = {s['to']: s['text'] for s in old['signs'] if s.get('from') == '乾'}
qian_new = {e[1]: e[2] for e in entries if e[0] == '乾'}
diff = [t for t in qian_old if t in qian_new and qian_old[t] != qian_new[t]]
print('乾节64条与旧库文本差异:', len(diff), diff[:5])
by_sec2 = {}
for f_, t_, tx in entries:
    by_sec2.setdefault(f_, []).append(t_)
sec_bad2 = [(s, len(ts)) for s, ts in by_sec2.items() if ts != SEQ[KINGWEN.index(s)]]
ok = len(entries) == 4096 and not sec_bad2 and not notes
if ok:
    missing = [f'{f_}之{t_}' for f_, t_, tx in entries if tx is None]
    out = {
        'meta': {
            'name': '焦氏易林4096签·卦变映射表',
            'structure': 'from(本卦,文王序)/to(之卦,文王序)/text(繇辞)；text=null=源缺（slot保留，引擎顺延规则见usage）',
            'source': '殆知阁·焦氏易林.txt（电子重排版，内容级；校勘引证以四库本为准）',
            'rebuild': '2026-10-11 批74 v5管线：序位锚定解析+裸名节界+断头抢救+旧库对照清洗/回填；64节×64条序列全校验',
            'missing_count': len(missing),
            'missing': missing,
            'usage': '真算引擎专用：梅花起卦得本卦+动爻→变卦→查 from==本卦&&to==变卦；slot缺则顺延至同本卦下一有签之位（确定性规则）',
        },
        'kingwen': KINGWEN,
        'signs': [{'from': f_, 'to': t_, 'text': tx} for f_, t_, tx in entries],
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'⑤落盘 {OUT}：4096 slot，实收 {4096-still_null}，缺 {still_null}')
else:
    print('!! 校验未过：entries', len(entries), 'sec_bad', sec_bad2[:5], 'notes', notes[:5])
    sys.exit(1)
