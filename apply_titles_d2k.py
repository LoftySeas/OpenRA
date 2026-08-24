#!/usr/bin/env python3
# D2K campaign map titles - Chinese only. No English mission names in this file.
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

zh_titles = {
    "atreides-01a": "亚特瑞斯 01a",
    "atreides-01b": "亚特瑞斯 01b",
    "atreides-02a": "亚特瑞斯 02a",
    "atreides-02b": "亚特瑞斯 02b",
    "atreides-03a": "亚特瑞斯 03a",
    "atreides-03b": "亚特瑞斯 03b",
    "atreides-04": "亚特瑞斯 04",
    "atreides-05": "亚特瑞斯 05",
    "harkonnen-01a": "哈科南 01a",
    "harkonnen-01b": "哈科南 01b",
    "harkonnen-02a": "哈科南 02a",
    "harkonnen-02b": "哈科南 02b",
    "harkonnen-03a": "哈科南 03a",
    "harkonnen-03b": "哈科南 03b",
    "harkonnen-04": "哈科南 04",
    "harkonnen-05": "哈科南 05",
    "harkonnen-06a": "哈科南 06a",
    "harkonnen-06b": "哈科南 06b",
    "harkonnen-07": "哈科南 07",
    "harkonnen-08": "哈科南 08",
    "harkonnen-09a": "哈科南 09a",
    "harkonnen-09b": "哈科南 09b",
    "ordos-01a": "厄尔德斯 01a",
    "ordos-01b": "厄尔德斯 01b",
    "ordos-02a": "厄尔德斯 02a",
    "ordos-02b": "厄尔德斯 02b",
    "ordos-03a": "厄尔德斯 03a",
    "ordos-03b": "厄尔德斯 03b",
    "ordos-04": "厄尔德斯 04",
    "ordos-05": "厄尔德斯 05",
    "ordos-06a": "厄尔德斯 06a",
}

maps_dir = 'D:/github/OpenRA/mods/d2k/maps'
applied = 0
for d, zh in zh_titles.items():
    yaml_path = os.path.join(maps_dir, d, 'map.yaml')
    zh_path = os.path.join(maps_dir, d, 'zh', 'map.ftl')
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
