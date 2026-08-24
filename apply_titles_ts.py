#!/usr/bin/env python3
# TS multiplayer map titles - Chinese only. No English mission names in this file.
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

zh_titles = {
    "1ice6": "无路可逃",
    "2temp7": "隐秘山谷",
    "ThePit": "深坑",
    "arivruns": "近在咫尺",
    "cityscap": "城市景观",
    "cliffsin": "疯狂峭壁",
    "drawbrid": "吊桥",
    "fields-of-green": "绿色原野",
    "float": "漂浮",
    "forestfr": "森林火灾",
    "karasjok": "卡拉肖克小镇",
    "ot11": "绿洲之困",
    "rivrrad4": "河道突袭",
    "springs": "热泉",
    "sunstroke": "中暑",
    "t_garden": "泰伯利亚花园",
    "tactical": "战术",
    "terrace": "梯田",
    "tiers": "悲伤之阶",
    "tread_l": "轻踏",
    "ts_rift": "裂隙",
    "uganda": "通往乌干达",
}

maps_dir = 'D:/github/OpenRA/mods/ts/maps'
applied = 0
for d, zh in zh_titles.items():
    yaml_path = os.path.join(maps_dir, d, 'map.yaml')
    zh_dir = os.path.join(maps_dir, d, 'zh')
    zh_path = os.path.join(zh_dir, 'map.ftl')
    if not os.path.exists(yaml_path):
        print('SKIP (no yaml): {0}'.format(d))
        continue
    with open(yaml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'^Title:\s*(.+)$', content, re.MULTILINE)
    if not m:
        print('SKIP (no Title): {0}'.format(d))
        continue
    en = m.group(1).strip()
    title_line = '## map.yaml\ntitle = "{0} ({1})"\n\n'.format(zh, en)
    existing = ''
    if os.path.exists(zh_path):
        with open(zh_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        if '## map.yaml' in existing and 'title' in existing:
            print('SKIP (already has title): {0}'.format(d))
            continue
    else:
        if not os.path.exists(zh_dir):
            os.makedirs(zh_dir)
    new_content = title_line + existing
    with open(zh_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    applied += 1
    print('OK: {0}'.format(d))

print('---')
print('Applied: {0} / {1}'.format(applied, len(zh_titles)))
