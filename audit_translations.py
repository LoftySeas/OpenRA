#!/usr/bin/env python3
import os, re

def audit(mod):
    maps_dir = f'D:/github/OpenRA/mods/{mod}/maps'
    declared = f'D:/github/OpenRA/mods/{mod}/missions.yaml'
    if not os.path.exists(declared):
        print(f'=== {mod}: no missions.yaml (no single-player campaign) ===')
        return
    done = set()
    for d in os.listdir(maps_dir):
        if os.path.isdir(os.path.join(maps_dir, d, 'zh')):
            done.add(d)
    groups = {}
    current = None
    with open(declared, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip()
            if re.match(r'^[A-Za-z].*:\s*$', line):
                current = line.rstrip(':').strip()
                groups[current] = []
            elif current and line.strip() and line.startswith(('\t', '  ')):
                groups[current].append(line.strip())
    print(f'=== {mod} ===')
    missing = []
    for g, ms in groups.items():
        if not ms: continue
        done_ct = sum(1 for m in ms if m in done)
        miss = [m for m in ms if m not in done]
        if miss:
            missing.extend(miss)
        print(f'  {g}: {done_ct} / {len(ms)}')
    print(f'  total maps with zh/: {len(done)}')
    if missing:
        print(f'  MISSING ({len(missing)}): {", ".join(missing)}')

for m in ['cnc', 'ra', 'd2k', 'ts']:
    audit(m)
    print()
