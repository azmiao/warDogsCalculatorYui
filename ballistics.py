# -*- coding: utf-8 -*-
"""弹道表加载与 MIL 仰角插值。

算法严格移植自参考项目 apollyon-sys/wardogs-calculator 的 js/features/weapons.js：
- 弹道表按距离分组，同距离多值取区间（minMil/maxMil）
- 命中分组：单值取该值，多值返回区间
- 未命中：定位左右相邻分组，右组取均值，左右各自取最接近的 mil 后线性插值
- 射程判定使用武器 minRange/maxRange，与弹道表覆盖范围相互独立
"""
import json
import os
from typing import Optional

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weapons.json')

_EPSILON = 1e-6


def _normalize_table(table) -> list[list[float]]:
    """清洗弹道表，过滤非法项，返回 [[distance, mil], ...]。"""
    if not isinstance(table, list):
        return []
    result = []
    for entry in table:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        try:
            distance = float(entry[0])
            mil = float(entry[1])
        except (TypeError, ValueError):
            continue
        result.append([distance, mil])
    return result


def _group_table(table: list[list[float]]) -> list[dict]:
    """按距离分组，同距离的多个 mil 合并为 mils 列表。"""
    grouped: list[dict] = []
    for distance, mil in sorted(table, key=lambda e: (e[0], e[1])):
        if grouped and grouped[-1]['distance'] == distance:
            grouped[-1]['mils'].append(mil)
            continue
        grouped.append({'distance': distance, 'mils': [mil]})
    return grouped


def _closest_mil(values: list[float], target: float) -> float:
    """返回列表中最接近 target 的 mil 值。"""
    return min(values, key=lambda v: abs(v - target))


def interpolate_ballistic_table(table: list[list[float]],
                                distance_meters: float) -> Optional[dict]:
    """按距离插值弹道表，返回 {'mil', 'minMil', 'maxMil'}，无法计算时返回 None。"""
    table = _normalize_table(table)
    if not table or distance_meters is None:
        return None

    groups = _group_table(table)

    # 精确命中某个距离分组
    for group in groups:
        if abs(group['distance'] - distance_meters) <= _EPSILON:
            min_mil = min(group['mils'])
            max_mil = max(group['mils'])
            return {
                'mil': group['mils'][0] if len(group['mils']) == 1 else None,
                'minMil': min_mil,
                'maxMil': max_mil,
            }

    # 定位左右相邻分组
    left = right = None
    for i in range(len(groups) - 1):
        if groups[i]['distance'] < distance_meters < groups[i + 1]['distance']:
            left, right = groups[i], groups[i + 1]
            break

    if left is None or right is None:
        return None

    right_average = sum(right['mils']) / len(right['mils'])
    left_mil = _closest_mil(left['mils'], right_average)
    right_mil = _closest_mil(right['mils'], left_mil)

    factor = (distance_meters - left['distance']) / (right['distance'] - left['distance'])
    mil = left_mil + factor * (right_mil - left_mil)

    return {'mil': mil, 'minMil': mil, 'maxMil': mil}


class Weapon:
    """单个武器的射程与弹道信息。"""

    def __init__(self, raw: dict):
        self.id: str = raw['id']
        self.names: dict = raw.get('names', {})
        self.min_range_km: float = float(raw['minRangeKm'])
        self.max_range_km: float = float(raw['maxRangeKm'])
        self.min_elevation_mil: Optional[float] = raw.get('minElevationMil')
        self.max_elevation_mil: Optional[float] = raw.get('maxElevationMil')
        ballistics = raw.get('ballistics') or {}
        self.single = _normalize_table(ballistics.get('single'))
        self.low = _normalize_table(ballistics.get('low'))
        self.high = _normalize_table(ballistics.get('high'))

    @property
    def name(self) -> str:
        return self.names.get('zh-cn') or self.names.get('en') or self.id

    def elevation_solutions(self, distance_meters: float) -> dict:
        """返回 {'inRange', 'single', 'low', 'high'} 四个仰角解。

        inRange 仅由射程决定，弹道表覆盖范围不参与判定（与参考项目一致）。
        """
        empty = {'inRange': False, 'single': None, 'low': None, 'high': None}
        if distance_meters is None:
            return empty

        min_meters = self.min_range_km * 1000
        max_meters = self.max_range_km * 1000
        in_range = (
            distance_meters + _EPSILON >= min_meters
            and distance_meters <= max_meters + _EPSILON
        )
        if not in_range:
            return {'inRange': False, 'single': None, 'low': None, 'high': None}

        return {
            'inRange': True,
            'single': interpolate_ballistic_table(self.single, distance_meters),
            'low': interpolate_ballistic_table(self.low, distance_meters),
            'high': interpolate_ballistic_table(self.high, distance_meters),
        }


class WeaponRegistry:
    """武器注册表，负责加载与别名查询。"""

    def __init__(self, data_path: str = _DATA_PATH):
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.weapons: dict[str, Weapon] = {
            item['id']: Weapon(item) for item in data.get('weapons', [])
        }
        self.default_id: str = data.get('default') or next(iter(self.weapons), None)
        self._aliases: dict[str, str] = {}
        self._build_aliases()

    def _build_aliases(self):
        # 固定中英文别名
        manual = {
            'mortar': ('迫击炮', 'l81', 'mortar', 'l81迫击炮', 'l81迫击炮'),
            'spg': ('榴弹炮', '自行火炮', 'sph2', 'sph-2', 'spg', 'sph2自行火炮'),
        }
        for wid in self.weapons:
            self._aliases[wid.lower()] = wid
            for name in self.weapons[wid].names.values():
                self._aliases[str(name).lower()] = wid
            for alias in manual.get(wid, ()):
                self._aliases[alias.lower()] = wid

    def get(self, weapon_id: str) -> Optional[Weapon]:
        return self.weapons.get(weapon_id)

    def resolve(self, text: str) -> Optional[Weapon]:
        """将用户输入的武器名/别名解析为武器，无法识别返回 None。"""
        if not text:
            return None
        key = text.strip().lower().replace(' ', '')
        wid = self._aliases.get(key)
        return self.weapons.get(wid) if wid else None

    @property
    def default(self) -> Optional[Weapon]:
        return self.weapons.get(self.default_id)

    def all_names(self) -> list[str]:
        """返回用于帮助提示的武器简称列表。"""
        return [w.name for w in self.weapons.values()]


registry = WeaponRegistry()
