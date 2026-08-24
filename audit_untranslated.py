#!/usr/bin/env python3
# Audit: find untranslated fluent keys and unregistered .ftl files.
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

def parse_ftl(path):
    """Return dict {key: value} from a Fluent .ftl file. Skips comments and blank lines."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            # Strip trailing comments - fluent uses # for line comments inside values
            # But for simplicity, only consider the simple "key = value" form on a single line
            # Multi-line values and select expressions are skipped - they're rare
            m = re.match(r'^([a-zA-Z][\w-]*)\s*=\s*(.+)$', line)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out

def is_english_text(s):
    """Heuristic: returns True if the string contains ASCII letters and looks like English text
    (not just identifiers/abbreviations)."""
    if not s:
        return False
    # If string has CJK chars, it's translated
    if re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', s):
        return False
    # If string is all-identifiers (dashes, no spaces, no verbs), skip
    if re.match(r'^[\w.-]+$', s):
        return False
    # If string has at least 2 English-looking words, mark as English
    words = re.findall(r'[A-Za-z]{2,}', s)
    return len(words) >= 2

mods = ['cnc', 'ra', 'ts', 'd2k']
mod_yaml_template = 'D:/github/OpenRA/mods/{0}/mod.yaml'

print('=' * 60)
print('A) Unregistered .ftl files (exist on disk but not in manifest)')
print('=' * 60)
for mod in mods:
    fluent_dir = 'D:/github/OpenRA/mods/{0}/fluent'.format(mod)
    yaml_path = mod_yaml_template.format(mod)
    if not os.path.exists(yaml_path):
        continue
    with open(yaml_path, 'r', encoding='utf-8') as f:
        manifest = f.read()
    on_disk = set()
    if os.path.exists(fluent_dir):
        for fn in os.listdir(fluent_dir):
            if fn.endswith('.ftl'):
                on_disk.add(fn)
    in_manifest = set(re.findall(r'\b(\w+\.ftl)\b', manifest))
    unregistered = on_disk - in_manifest
    if unregistered:
        print('  {0}: {1}'.format(mod, sorted(unregistered)))
    else:
        print('  {0}: OK ({1} files registered)'.format(mod, len(in_manifest)))

print()
print('=' * 60)
print('B) Untranslated keys (in en .ftl but missing or still English in zh/)')
print('=' * 60)
for mod in mods:
    en_dir = 'D:/github/OpenRA/mods/{0}/fluent'.format(mod)
    zh_dir = 'D:/github/OpenRA/mods/{0}/fluent/zh'.format(mod)
    if not os.path.exists(en_dir):
        continue
    files = sorted([fn for fn in os.listdir(en_dir) if fn.endswith('.ftl')])
    for fn in files:
        en = parse_ftl(os.path.join(en_dir, fn))
        zh = parse_ftl(os.path.join(zh_dir, fn))
        # Keys in en but not in zh
        missing = set(en.keys()) - set(zh.keys())
        # Keys in zh but value still looks English
        still_english = []
        for k, v in zh.items():
            if k in en and is_english_text(v):
                still_english.append((k, v, en[k]))
        if missing or still_english:
            print('  {0}/{1}:'.format(mod, fn))
            if missing:
                sample = sorted(missing)[:10]
                print('    MISSING in zh/ ({0} keys): {1}{2}'.format(
                    len(missing), ', '.join(sample), '...' if len(missing) > 10 else ''))
            for k, zh_v, en_v in still_english[:5]:
                print('    STILL-ENGLISH: {0} = "{1}" (en: "{2}")'.format(k, zh_v, en_v))
            if len(still_english) > 5:
                print('    ... and {0} more still-English keys'.format(len(still_english) - 5))
