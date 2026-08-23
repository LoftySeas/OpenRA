#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Translate the common hotkeys.ftl by mapping known English descriptions to Chinese.

Reads D:/github/OpenRA/mods/common/fluent/hotkeys.ftl (English) and overwrites
the Chinese sibling with a complete translation. Keeps key order and the leading
'## section' comments intact. Keys not in the dictionary are emitted unchanged
so a human reviewer can pick them up.
"""
import re
import sys

EN_PATH = r'D:\github\OpenRA\mods\common\fluent\hotkeys.ftl'
ZH_PATH = r'D:\github\OpenRA\mods\common\fluent\zh\hotkeys.ftl'

# Specific translations (literal map). Keys that do not appear here are derived
# from the patterns below.
EXACT = {
    'Open Team Chat': '打开队伍聊天',
    'Open General Chat': '打开公共聊天',
    'Toggle Chat Mode': '切换聊天模式',
    'Autocomplete': '自动补全',
    'Remove from control group': '从编队移除',
    'Undo': '撤销',
    'Redo': '重做',
    'Copy': '复制',
    'Save Map': '保存地图',
    'Paste': '粘贴',
    'Delete Selection': '删除选择',
    'Select Tab': '选择标签页',
    'Tiles Tab': '地块标签页',
    'Overlays Tab': '覆盖物标签页',
    'Actors Tab': '单位标签页',
    'Tools Tab': '工具标签页',
    'History Tab': '历史标签页',
    'Settings Tab': '设置标签页',
    'Grid Overlay': '网格覆盖',
    'Buildable Terrain Overlay': '可建造地形覆盖',
    'Marker Layer Overlay': '标记层覆盖',
    'Jump to base': '跳转至基地',
    'Jump to last radar event': '跳转至最近雷达事件',
    'Jump to selection': '跳转至选择',
    'Select all combat units': '选择所有战斗单位',
    'Select units by type': '按类型选择单位',
    'Cycle Harvesters': '切换采矿车',
    'Pause / Unpause': '暂停 / 取消暂停',
    'Sell mode': '出售模式',
    'Repair mode': '维修模式',
    'Place beacon': '放置信标',
    'Cycle status bars display': '切换状态栏显示',
    'Toggle audio mute': '切换静音',
    'Toggle relationship colors': '切换关系颜色',
    'Take screenshot': '截图',
    'Attack Move': '攻击移动',
    'Stop': '停止',
    'Scatter': '散开',
    'Deploy': '部署',
    'Guard': '守卫',
    'Attack anything': '攻击任何目标',
    'Defend': '防御',
    'Return fire': '还击',
    'Hold fire': '停火',
    'Disable statistics': '关闭统计',
    'Basic statistics': '基本统计',
    'Economy statistics': '经济统计',
    'Production statistics': '生产统计',
    'Support Power statistics': '支援技能统计',
    'Combat statistics': '战斗统计',
    'Army statistics': '军队统计',
    'Statistics graph': '统计图表',
    'Army value graph': '军队价值图表',
    'Next facility': '下一建筑',
    'Current facility': '当前建筑',
    'All Players': '所有玩家',
    'Disable Shroud': '关闭战争迷雾',
    'Slow speed': '慢速',
    'Regular speed': '常速',
    'Fast speed': '快速',
    'Maximum speed': '最快',
    'Previous': '上一首',
    'Next': '下一首',
    'Pause or Resume': '暂停或继续',
    'Scroll up': '向上滚动',
    'Scroll down': '向下滚动',
    'Scroll left': '向左滚动',
    'Scroll right': '向右滚动',
    'Jump to top edge': '跳转至地图顶端',
    'Jump to bottom edge': '跳转至地图底端',
    'Jump to left edge': '跳转至地图左端',
    'Jump to right edge': '跳转至地图右端',
    'Record bookmark 1': '记录书签 1',
    'Jump to bookmark 1': '跳转至书签 1',
    'Record bookmark 2': '记录书签 2',
    'Jump to bookmark 2': '跳转至书签 2',
    'Record bookmark 3': '记录书签 3',
    'Jump to bookmark 3': '跳转至书签 3',
    'Record bookmark 4': '记录书签 4',
    'Jump to bookmark 4': '跳转至书签 4',
    'Zoom in': '放大',
    'Zoom out': '缩小',
    'Reset zoom': '重置缩放',
    'Disable User Interface': '隐藏界面',
    'Disable Extra User Interface': '隐藏额外界面',
}

PATTERNS = [
    # "Select group N" -> "选择编队 N"
    (re.compile(r'^Select group (\d+)$'), lambda m: f'选择编队 {m.group(1)}'),
    # "Create group N" -> "编组 N"
    (re.compile(r'^Create group (\d+)$'), lambda m: f'编组 {m.group(1)}'),
    # "Add to group N" -> "加入编队 N"
    (re.compile(r'^Add to group (\d+)$'), lambda m: f'加入编队 {m.group(1)}'),
    # "Combine with group N" -> "与编队 N 合并"
    (re.compile(r'^Combine with group (\d+)$'), lambda m: f'与编队 {m.group(1)} 合并'),
    # "Jump to group N" -> "跳转至编队 N"
    (re.compile(r'^Jump to group (\d+)$'), lambda m: f'跳转至编队 {m.group(1)}'),
    # "Slot NN" -> "栏位 NN"
    (re.compile(r'^Slot (\d+)$'), lambda m: f'栏位 {m.group(1)}'),
]


def translate(en_value: str) -> str:
    if en_value in EXACT:
        return EXACT[en_value]
    for pat, fn in PATTERNS:
        m = pat.match(en_value)
        if m:
            return fn(m)
    return en_value  # unchanged - human review needed


def main():
    with open(EN_PATH, encoding='utf-8') as f:
        lines = f.readlines()

    out = []
    out.append('## Translated from common/fluent/hotkeys.ftl\n')
    untranslated = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith('##'):
            out.append(line)
            continue
        m = re.match(r'^([a-z][a-z0-9-]*) = (.*)$', line.rstrip('\n'))
        if not m:
            out.append(line)
            continue
        key, val = m.group(1), m.group(2)
        translated = translate(val)
        out.append(f'{key} = {translated}\n')
        if translated == val:
            untranslated.append(key)

    with open(ZH_PATH, 'w', encoding='utf-8') as f:
        f.writelines(out)

    print(f'Wrote {len(out)} lines to {ZH_PATH}')
    print(f'Untranslated keys (need human review): {len(untranslated)}')
    for k in untranslated:
        print(f'  {k}')


if __name__ == '__main__':
    main()
