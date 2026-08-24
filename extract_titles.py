#!/usr/bin/env python3
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

# Extract English title from map.yaml for all maps in cnc, d2k, ts
for mod in ['cnc', 'd2k', 'ts']:
    maps_dir = 'D:/github/OpenRA/mods/{0}/maps'.format(mod)
    print('=== {0} ==='.format(mod))
    for d in sorted(os.listdir(maps_dir)):
        yaml = os.path.join(maps_dir, d, 'map.yaml')
        if not os.path.exists(yaml): continue
        with open(yaml, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'^Title:\s*(.+)$', content, re.MULTILINE)
        title = m.group(1).strip() if m else '???'
        has_zh = os.path.exists(os.path.join(maps_dir, d, 'zh'))
        print('  {0:40s}  {1}  | {2}'.format(d, 'zh' if has_zh else '--', title))
