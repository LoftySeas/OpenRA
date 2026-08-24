#!/usr/bin/env python3
import os
for mod in ['cnc', 'd2k', 'ra', 'ts']:
    maps_dir = 'D:/github/OpenRA/mods/{0}/maps'.format(mod)
    if not os.path.exists(maps_dir): continue
    with_title = 0
    total = 0
    for d in os.listdir(maps_dir):
        zh = os.path.join(maps_dir, d, 'zh', 'map.ftl')
        if os.path.exists(zh):
            total += 1
            with open(zh, 'r', encoding='utf-8') as f:
                content = f.read()
            if '## map.yaml' in content and 'title' in content:
                with_title += 1
    print('{0}: {1} / {2} zh/map.ftl files have a title key'.format(mod, with_title, total))
