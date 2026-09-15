"""从参考项目导出的原始 weapons.raw.json 生成插件精简武器数据。

仅做字段裁剪与中文名补全，弹道表原样保留以保证插值精度。
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# 武器显示名（zh-cn），参考项目 spg 缺少中文名，这里补齐
ZH_NAMES = {
    'mortar': 'L81 迫击炮',
    'spg': 'SPH-2 自行火炮',
}


def main():
    with open(os.path.join(_ROOT, 'weapons.raw.json'), encoding='utf-8') as f:
        raw = json.load(f)

    out = {'default': raw.get('default', 'mortar'), 'weapons': []}
    for item in raw['weapons']:
        wid = item['id']
        names = dict(item.get('names', {}))
        names['zh-cn'] = ZH_NAMES.get(wid, names.get('zh-cn', wid))

        ballistics = {}
        for key in ('single', 'low', 'high'):
            table = item.get('ballistics', {}).get(key)
            if table:
                ballistics[key] = [[int(d), int(m)] for d, m in table]

        out['weapons'].append({
            'id': wid,
            'names': names,
            'minRangeKm': item['minRangeKm'],
            'maxRangeKm': item['maxRangeKm'],
            'minElevationMil': item.get('minElevationMil'),
            'maxElevationMil': item.get('maxElevationMil'),
            'ballistics': ballistics,
        })

    target = os.path.join(_ROOT, 'weapons.json')
    with open(target, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'written {target}')


if __name__ == '__main__':
    main()
