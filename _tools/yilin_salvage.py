# -*- coding: utf-8 -*-
"""易林缺签抢救：82个缺签slot中，"头部断行、繇辞并入前条"的损伤可定向切分还原。
规则：缺签X之Y → 查前一条text中是否有'。X之Y前缀'形态的断头（头前必为句号/起头），
切分：前段还前条，后段归缺签slot。全部决策打印供人工复核；歧义不动作留null。"""
import json, re

P = 'skill-coin-knows/assets/yilin_hexagrams.json'
d = json.load(open(P, encoding='utf-8'))
signs = d['signs']
KINGWEN = d['kingwen']
IDX = set(KINGWEN)
ALIAS_REV = {}  # 断头可能用别名形态

def is_name_frag(s):
    """s是否像卦名前缀：非空、无标点、且能匹配某卦名前缀"""
    if not s or re.search(r'[，。；！？、\u3000\s]', s):
        return False
    return any(k.startswith(s) or s.startswith(k) for k in IDX)

salvaged, kept_null, suspicious = [], [], []
for i, e in enumerate(signs):
    if e['text'] is not None:
        continue
    X, Y = e['from'], e['to']
    if i == 0:
        kept_null.append((X, Y, '首条无前条'))
        continue
    prev = signs[i-1]
    if prev['text'] is None:
        kept_null.append((X, Y, '前条亦缺'))
        continue
    # 断头形态A：全名头截断 '。X之Y前缀...'（头前为句号或text起头）
    cands = []
    for m in re.finditer(r'(?:^|。)%s之([^\u3000，。；！？\n]{1,3})' % re.escape(X), prev['text']):
        frag = m.group(1)
        if Y.startswith(frag) or frag == Y:   # 截断前缀匹配目标之卦
            head_end = m.end()
            verse = prev['text'][head_end:]
            head_part = prev['text'][:head_end]
            if 10 <= len(verse) <= 150 and '。' in verse:
                cands.append(('A', m.start(), head_part, verse))
    # 断头形态B：短头丢失但留了'之卦名+全角空格'残段（如 '　中　'）
    for m in re.finditer(r'(?:^|。)\u3000?([^\u3000，。；！？\n]{1,3})\u3000+', prev['text']):
        frag = m.group(1)
        if Y.startswith(frag):
            verse = prev['text'][m.end():]
            if 10 <= len(verse) <= 150 and '。' in verse:
                cands.append(('B', m.start(), prev['text'][:m.end()], verse))
    if len(cands) == 1:
        kind, pos, head_part, verse = cands[0]
        salvaged.append((X, Y, kind, prev['text'][:40], verse[:40]))
        signs[i-1]['text'] = head_part if head_part.endswith('。') or head_part == '' else head_part
        signs[i-1]['text'] = prev['text'][:pos] if pos > 0 else ''
        if not signs[i-1]['text']:
            signs[i-1]['text'] = None
        e['text'] = verse
    elif len(cands) > 1:
        suspicious.append((X, Y, f'{len(cands)}个候选，不动作'))
    else:
        kept_null.append((X, Y, '前条无断头形态'))

print(f'抢救成功: {len(salvaged)}')
for s in salvaged:
    print('  ✓', s[0], '之', s[1], f'[{s[2]}] 前条尾:…{s[3][-24:]} | 还原: {s[4]}…')
print(f'留null: {len(kept_null)}')
for s in kept_null:
    print('  ·', s[0], '之', s[1], '—', s[2])
print(f'歧义: {len(suspicious)}')
for s in suspicious:
    print('  ?', s)

# 污染扫描：所有已收text内不得再有"句号+X之Y前缀"断头形态
contam = []
for i, e in enumerate(signs):
    if e['text'] is None:
        continue
    for m in re.finditer(r'(?:^|。)([^\u3000，。；！？\n]{1,2})之([^\u3000，。；！？\n]{1,3})([^\u3000，。；！？\n])', e['text']):
        a, b, nxt = m.groups()
        if a in IDX and (b in IDX or is_name_frag(b)) and is_name_frag(b+nxt if len(b+nxt)<=3 else b):
            contam.append((e['from'], e['to'], e['text'][max(0,m.start()-6):m.end()+10]))
print(f'残留污染: {len(contam)}')
for c in contam[:10]:
    print('  !', c)

filled = sum(1 for e in signs if e['text'])
d['meta']['salvage'] = f'批74抢救：断头切分还原{len(salvaged)}条；终态实收{filled}/4096，缺{4096-filled}条（殆知阁源损，slot如实保留null）'
d['meta']['missing_count'] = 4096 - filled
d['meta']['missing'] = [f"{e['from']}之{e['to']}" for e in signs if e['text'] is None]
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已回写。终态实收', filled, '/4096')
