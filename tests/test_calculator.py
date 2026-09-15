"""计算核心的交叉验证测试。

reference.json 由 tests/gen_reference.js 调用参考项目原始 JS 函数生成，
本测试逐项比对 Python 移植实现，确保零偏差。

运行：python tests/test_calculator.py
"""
import json
import math
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.dirname(_HERE)
_PKG_PARENT = os.path.dirname(_PKG_DIR)
_PKG_NAME = 'warDogsCalculatorYui'

# 注入轻量包，隔离纯逻辑模块，避免导入插件 __init__ 触发框架初始化
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
if _PKG_NAME not in sys.modules:
    _pkg = types.ModuleType(_PKG_NAME)
    _pkg.__path__ = [_PKG_DIR]
    sys.modules[_PKG_NAME] = _pkg

from warDogsCalculatorYui import calculator as calc
from warDogsCalculatorYui.ballistics import registry

with open(os.path.join(_HERE, 'reference.json'), encoding='utf-8') as f:
    REFERENCE = json.load(f)


def _close(a, b, tol=1e-6):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _check_solution(py_sol, js_sol, ctx):
    if (py_sol is None) != (js_sol is None):
        raise AssertionError(f'{ctx}: 解的存在性不一致 py={py_sol} js={js_sol}')
    if py_sol is None:
        return
    for key in ('mil', 'minMil', 'maxMil'):
        if not _close(py_sol[key], js_sol[key]):
            raise AssertionError(
                f'{ctx}: {key} 不一致 py={py_sol[key]} js={js_sol[key]}',
            )


def test_ballistics_matches_reference():
    count = 0
    for wid, samples in REFERENCE.items():
        weapon = registry.get(wid)
        assert weapon is not None, f'武器 {wid} 未加载'
        for distance_str, js_sol in samples.items():
            distance = float(distance_str)
            py_sol = weapon.elevation_solutions(distance)
            ctx = f'{wid}@{distance}m'
            assert py_sol['inRange'] == js_sol['inRange'], f'{ctx}: inRange 不一致'
            for key in ('single', 'low', 'high'):
                _check_solution(py_sol[key], js_sol[key], f'{ctx}.{key}')
            count += 1
    print(f'[OK] 弹道插值交叉验证通过，共 {count} 个采样点')
    return count


def test_distance_azimuth():
    weapon = registry.get('mortar')
    # 正东 100m：dx=1, dy=0 -> 方位角 90°，距离 100m
    sol = calc.calculate(weapon, calc.Point(105, 115), calc.Point(106, 115))
    assert _close(sol.distance_m, 100), sol.distance_m
    assert _close(sol.azimuth, 90), sol.azimuth
    assert _close(sol.dx_m, 100), sol.dx_m
    assert _close(sol.dy_m, 0), sol.dy_m

    # 正北：dy=1 -> 方位角 0°
    sol = calc.calculate(weapon, calc.Point(105, 115), calc.Point(105, 116))
    assert _close(sol.azimuth, 0), sol.azimuth

    # 正南：dy=-1 -> 方位角 180°
    sol = calc.calculate(weapon, calc.Point(105, 115), calc.Point(105, 114))
    assert _close(sol.azimuth, 180), sol.azimuth

    # 正西：dx=-1 -> 方位角 270°
    sol = calc.calculate(weapon, calc.Point(105, 115), calc.Point(104, 115))
    assert _close(sol.azimuth, 270), sol.azimuth

    # 西北：dx=-1, dy=1 -> 方位角 315°
    sol = calc.calculate(weapon, calc.Point(105, 115), calc.Point(104, 116))
    assert _close(sol.azimuth, 315), sol.azimuth

    # 3-4-5 直角三角形：dx=3, dy=4 -> 距离 500m，方位角 atan2(3,4)=36.87°
    sol = calc.calculate(weapon, calc.Point(100, 100), calc.Point(103, 104))
    assert _close(sol.distance_m, 500), sol.distance_m
    assert _close(sol.azimuth, math.degrees(math.atan2(3, 4))), sol.azimuth

    print('[OK] 距离与方位角计算通过')


def test_range_boundary():
    weapon = registry.get('mortar')
    # 射程内
    sol = calc.calculate(weapon, calc.Point(0, 0), calc.Point(0, 2))  # 200m
    assert sol.in_range is True
    # 超远：dy=7 -> 700m > 684m
    sol = calc.calculate(weapon, calc.Point(0, 0), calc.Point(0, 7))
    assert sol.in_range is False
    # 过近：dy=1 -> 100m < 132m
    sol = calc.calculate(weapon, calc.Point(0, 0), calc.Point(0, 1))
    assert sol.in_range is False
    print('[OK] 射程边界判定通过')


def test_coordinate_parsing():
    # 单个坐标点（各种不规范写法）
    single_cases = [
        ('105 115', calc.Point(105, 115)),
        ('X105 Y115', calc.Point(105, 115)),
        ('x:105, y:115', calc.Point(105, 115)),
        ('x105.5 y115.25', calc.Point(105.5, 115.25)),
        ('x105.5,y115.25', calc.Point(105.5, 115.25)),
        ('x97.43, y109.27', calc.Point(97.43, 109.27)),
        ('105\t115', calc.Point(105, 115)),
        ('y109.27 x97.43', calc.Point(97.43, 109.27)),  # 标签乱序也能按语义配对
    ]
    for text, expected in single_cases:
        point = calc.parse_coordinates(text)
        assert point is not None, f'{text!r} 解析失败'
        assert _close(point.x, expected.x) and _close(point.y, expected.y), \
            f'{text!r} -> {point}, 期望 {expected}'

    # 无法解析为一个点的输入
    for bad in ['', 'abc', '105', '1 2 3', 'x105', 'x105 y']:
        assert calc.parse_coordinates(bad) is None, f'{bad!r} 不应解析成功'
    print('[OK] 单坐标解析通过')


def test_extract_points():
    """覆盖用户从游戏复制的各种坐标写法，均应解析出两个点。"""
    p1 = (97.43, 109.27)
    p2 = (100.5, 120.3)
    cases = [
        # 带 x/y 标签，空格 / 逗号 / 分号 / 换行分隔
        'x97.43, y109.27 x100.5, y120.3',
        'x97.43, y109.27, x100.5, y120.3',
        'x97.43,y109.27,x100.5,y120.3',
        'x97.43 y109.27 x100.5 y120.3',
        'x97.43, y109.27\nx100.5, y120.3',
        'X97.43, Y109.27 X100.5, Y120.3',
        'x:97.43 y:109.27 x:100.5 y:120.3',
        # 无标签，纯数字两两配对
        '97.43 109.27 100.5 120.3',
        '97.43,109.27,100.5,120.3',
        '97.43, 109.27, 100.5, 120.3',
        # 全角标点
        'x97.43，y109.27 x100.5，y120.3',
        # 括号包裹
        '(97.43, 109.27) (100.5, 120.3)',
    ]
    for text in cases:
        points = calc.extract_points(text)
        assert len(points) == 2, f'{text!r} -> {points}'
        assert _close(points[0].x, p1[0]) and _close(points[0].y, p1[1]), \
            f'{text!r} 第一点错误 -> {points[0]}'
        assert _close(points[1].x, p2[0]) and _close(points[1].y, p2[1]), \
            f'{text!r} 第二点错误 -> {points[1]}'

    # 数量不足或为奇数时不应解析出两个点
    for bad in ['', '97.43', '97.43 109.27 100.5']:
        assert len(calc.extract_points(bad)) != 2, f'{bad!r} 不应解析出两个坐标点'
    # 恰好一个完整坐标点
    assert len(calc.extract_points('x97.43 y109.27')) == 1
    print('[OK] 多坐标容错解析通过')


def test_weapon_alias():
    for alias in ('迫击炮', 'l81', 'L81', 'mortar'):
        assert registry.resolve(alias).id == 'mortar', alias
    for alias in ('榴弹炮', 'sph2', 'SPH-2', 'spg', '自行火炮'):
        assert registry.resolve(alias).id == 'spg', alias
    assert registry.resolve('不存在') is None
    print('[OK] 武器别名解析通过')


def test_mil_text_format():
    weapon = registry.get('mortar')
    sol = calc.calculate(weapon, calc.Point(0, 0), calc.Point(0, 2))  # 200m -> 788
    assert sol.mil_text == '788', sol.mil_text

    spg = registry.get('spg')
    # 2629m 高角为区间 610-620，低角 600
    sol = calc.calculate(spg, calc.Point(0, 0), calc.Point(0, 26.29))
    assert sol.mil_text == '600 / 610–620', sol.mil_text
    assert sol.mil_detail == '低角 / 高角', sol.mil_detail
    print('[OK] MIL 文本格式化通过')


def test_parse_weapon_and_points():
    # 带武器 + 两个坐标点
    weapon, points = calc.parse_weapon_and_points('迫击炮 105 115 110 120')
    assert weapon.id == 'mortar', weapon
    assert [(p.x, p.y) for p in points] == [(105, 115), (110, 120)], points

    # 带武器 + x/y 标签坐标
    weapon, points = calc.parse_weapon_and_points('sph2 x97.43, y109.27 x100.5, y120.3')
    assert weapon.id == 'spg', weapon
    assert _close(points[0].x, 97.43) and _close(points[1].y, 120.3), points

    # 无武器，仅坐标
    weapon, points = calc.parse_weapon_and_points('105 115 110 120')
    assert weapon is None
    assert len(points) == 2, points

    # 仅武器
    weapon, points = calc.parse_weapon_and_points('榴弹炮')
    assert weapon.id == 'spg', weapon
    assert points == [], points

    # 空输入
    weapon, points = calc.parse_weapon_and_points('')
    assert weapon is None and points == []

    # 小数坐标
    weapon, points = calc.parse_weapon_and_points('迫击炮 105.5 115.25 110 120')
    assert weapon.id == 'mortar'
    assert [(p.x, p.y) for p in points] == [(105.5, 115.25), (110, 120)], points
    print('[OK] 命令解析通过')


if __name__ == '__main__':
    test_ballistics_matches_reference()
    test_distance_azimuth()
    test_range_boundary()
    test_coordinate_parsing()
    test_extract_points()
    test_weapon_alias()
    test_mil_text_format()
    test_parse_weapon_and_points()
    print('\n[PASS] 全部测试通过')
