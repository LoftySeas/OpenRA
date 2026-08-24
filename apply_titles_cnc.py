#!/usr/bin/env python3
# CNC campaign map titles - Chinese only. No English mission names in this file.
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

# Key = map directory name, value = Chinese title
zh_titles = {
    "cnc64gdi01": "C&C64 特种行动 - GDI 1",
    "eviction-notice": "Nod - 驱逐通知",
    "funpark01": "异常行为",
    "gdi01": "01：突袭滩头",
    "gdi02": "02：摧毁炼油厂",
    "gdi03": "03：摧毁防空导弹",
    "gdi04a": "04a：取回离子炮",
    "gdi04b": "04b：取回离子炮",
    "gdi04c": "04c：夺取比亚韦斯托克",
    "gdi05a": "05a：修复 GDI 基地",
    "gdi05b": "05b：修复 GDI 基地",
    "gdi05c": "05c：修复 GDI 基地",
    "gdi06": "06：渗透 Nod 基地",
    "gdi07": "07：终结 Nod 基地",
    "gdi08a": "08a：重夺萨尔茨堡",
    "gdi08b": "08b：保卫莫比乌斯",
    "gdi09": "09：守备多瑙河",
    "nod01": "01：尼库巴之死",
    "nod02a": "02a：入侵埃及",
    "nod02b": "02b：入侵埃及",
    "nod03a": "03a：苏丹出逃",
    "nod03b": "03b：苏丹出逃",
    "nod04a": "04a：乌姆哈杰尔",
    "nod04b": "04b：毛派内战",
    "nod05": "05：猎杀战车",
    "nod06a": "06a：回收起爆器",
    "nod06b": "06b：回收起爆器",
    "nod06c": "06c：回收起爆器",
    "nod07a": "07a：病入膏肓",
    "nod07b": "07b：病入膏肓",
    "nod07c": "07c：回收飞艇",
    "nod08a": "08a：扎伊尔之战",
    "nod08b": "08b：扎伊尔之战",
    "nod09": "09：增援埃及",
    "nod10a": "10a：完成王博士",
    "nod10b": "10b：拆除猛犸坦克工厂",
    "the-tiberium-strain": "Nod - 泰伯利亚变种",
    "twist-of-fate": "GDI - 命运的转折",
}

maps_dir = 'D:/github/OpenRA/mods/cnc/maps'
applied = 0
for d, zh in zh_titles.items():
    yaml_path = os.path.join(maps_dir, d, 'map.yaml')
    zh_dir = os.path.join(maps_dir, d, 'zh')
    zh_path = os.path.join(zh_dir, 'map.ftl')
    if not os.path.exists(yaml_path):
        print('SKIP (no yaml): {0}'.format(d))
        continue
    if not os.path.exists(zh_path):
        print('SKIP (no zh): {0}'.format(d))
        continue
    with open(yaml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'^Title:\s*(.+)$', content, re.MULTILINE)
    if not m:
        print('SKIP (no Title): {0}'.format(d))
        continue
    en = m.group(1).strip()
    title_line = '## map.yaml\ntitle = "{0} ({1})"\n\n'.format(zh, en)
    with open(zh_path, 'r', encoding='utf-8') as f:
        existing = f.read()
    if '## map.yaml' in existing and 'title' in existing:
        print('SKIP (already has title): {0}'.format(d))
        continue
    new_content = title_line + existing
    with open(zh_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    applied += 1
    print('OK: {0}'.format(d))

print('---')
print('Applied: {0} / {1}'.format(applied, len(zh_titles)))
