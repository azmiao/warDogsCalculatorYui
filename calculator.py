# -*- coding: utf-8 -*-
"""射击诸元计算核心。

计算公式严格对齐参考项目 apollyon-sys/wardogs-calculator：
- 坐标换算：1 坐标 = 100 米（三张地图一致）
- 距离：hypot(dx, dy) * 100 米
- 方位角：atan2(dx, dy) 转角度，负值 +360（正北 0°，顺时针）
- ΔX / ΔY：带符号的水平分量（米）
- MIL 仰角：由弹道表按距离插值，L81 单解、SPH-2 低/高角双解
"""
import math
import re
from dataclasses import dataclass
from typing import Optional

from .ballistics import Weapon, registry

# 每 1 个游戏坐标对应的物理距离（米）
METERS_PER_UNIT = 100


@dataclass
class Point:
    """地图坐标点。"""
    x: float
    y: float


@dataclass
class FireSolution:
    """一次完整的射击诸元计算结果。"""
    weapon: Weapon
    origin: Point
    target: Point
    distance_m: float
    distance_km: float
    azimuth: float
    dx_m: float
    dy_m: float
    in_range: bool
    min_range_m: float
    max_range_m: float
    solutions: dict

    @property
    def mil_text(self) -> str:
        """主仰角文本，如 '720'、'520–540' 或 '低角 620 / 高角 1180'。"""
        s = self.solutions
        if s.get('single'):
            return _format_solution(s['single'])
        if s.get('low') and s.get('high'):
            return f"{_format_solution(s['low'])} / {_format_solution(s['high'])}"
        if s.get('low'):
            return _format_solution(s['low'])
        if s.get('high'):
            return _format_solution(s['high'])
        return '—'

    @property
    def mil_detail(self) -> str:
        """仰角补充说明，如 '低角 / 高角' 或 '无解'。"""
        s = self.solutions
        if s.get('single'):
            return ''
        if s.get('low') and s.get('high'):
            return '低角 / 高角'
        if s.get('low'):
            return '低角'
        if s.get('high'):
            return '高角'
        if s.get('inRange'):
            return '该距离无弹道解'
        return ''


def _js_round(value: float) -> int:
    """模拟 JavaScript Math.round（四舍五入，.5 向上），与参考项目输出一致。"""
    return math.floor(value + 0.5)


def _format_solution(solution: dict) -> str:
    """将插值解格式化为文本，多值显示为区间。"""
    if not solution:
        return '—'
    min_mil = _js_round(solution['minMil'])
    max_mil = _js_round(solution['maxMil'])
    if min_mil != max_mil:
        return f'{min_mil}–{max_mil}'
    return str(_js_round(solution.get('mil', min_mil)))


# 数字（支持正负号、小数、小数点或逗号分隔）
_NUM_PATTERN = r'[+-]?\d+(?:[.,]\d+)?'
# 带标签的坐标：x105 y115 或 x:105, y:115
_LABELED_X = re.compile(rf'(?:^|[^a-z])x\s*[:=]?\s*({_NUM_PATTERN})', re.IGNORECASE)
_LABELED_Y = re.compile(rf'(?:^|[^a-z])y\s*[:=]?\s*({_NUM_PATTERN})', re.IGNORECASE)
_ALL_NUMBERS = re.compile(_NUM_PATTERN)


def _to_float(raw: str) -> float:
    return float(str(raw).replace(',', '.'))


def parse_coordinates(text: str) -> Optional[Point]:
    """解析用户输入的坐标。

    支持 'X105 Y115'、'x:105, y:115'、'105 115'、'105,115' 等写法。
    无法解析出两个数字时返回 None。
    """
    if not text:
        return None
    text = str(text).strip()
    if not text:
        return None

    x_match = _LABELED_X.search(text)
    y_match = _LABELED_Y.search(text)
    if x_match and y_match:
        return Point(_to_float(x_match.group(1)), _to_float(y_match.group(1)))

    numbers = _ALL_NUMBERS.findall(text)
    if len(numbers) != 2:
        return None
    return Point(_to_float(numbers[0]), _to_float(numbers[1]))


def calculate(weapon: Weapon, origin: Point, target: Point) -> FireSolution:
    """根据炮位与目标坐标计算完整射击诸元。"""
    dx = target.x - origin.x
    dy = target.y - origin.y

    distance_m = math.hypot(dx, dy) * METERS_PER_UNIT

    azimuth = math.degrees(math.atan2(dx, dy))
    if azimuth < 0:
        azimuth += 360

    solutions = weapon.elevation_solutions(distance_m)

    return FireSolution(
        weapon=weapon,
        origin=origin,
        target=target,
        distance_m=distance_m,
        distance_km=distance_m / 1000,
        azimuth=azimuth,
        dx_m=dx * METERS_PER_UNIT,
        dy_m=dy * METERS_PER_UNIT,
        in_range=solutions['inRange'],
        min_range_m=weapon.min_range_km * 1000,
        max_range_m=weapon.max_range_km * 1000,
        solutions=solutions,
    )
