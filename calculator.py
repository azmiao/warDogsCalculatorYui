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
import unicodedata
from dataclasses import dataclass

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
    origin_locked: bool = False

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


# 单个数字：支持正负号与小数（小数点或逗号作小数分隔符）
_NUM_PATTERN = r'[+-]?\d+(?:[.,]\d+)?'
# 带 x/y 标签的坐标，如 x97.43、y109.27、x:97、y=109（前面不能紧跟字母，避免误匹配单词）
_LABEL_TOKEN = re.compile(rf'(?<![a-z])([xy])\s*[:=]?\s*({_NUM_PATTERN})', re.IGNORECASE)
_NUMBER = re.compile(_NUM_PATTERN)


def _normalize(text: str) -> str:
    """全角转半角，统一逗号、冒号、括号等标点，便于容错解析。"""
    return unicodedata.normalize('NFKC', str(text))


def _to_float(raw: str) -> float:
    return float(str(raw).replace(',', '.'))


def extract_points(text: str) -> list[Point]:
    """从文本中解析坐标点列表，尽量兼容各种不规范输入。

    解析优先级：
    1. 带 x/y 标签时按标签语义配对（与出现顺序无关）
       例：'x97.43, y109.27'、'x97.43 y109.27'、'x:97.43, y:109.27'
    2. 无标签时按数字出现顺序两两配对
       例：'97.43 109.27'、'97.43,109.27'、'97.43, 109.27'

    多个坐标点可用空格、逗号、分号、换行等任意分隔，坐标数量为偶数时返回。
    """
    if not text:
        return []
    text = _normalize(text)

    # 优先按 x/y 标签配对，避免出现顺序打乱导致的错配
    labels = _LABEL_TOKEN.findall(text)
    if labels:
        xs = [_to_float(v) for k, v in labels if k.lower() == 'x']
        ys = [_to_float(v) for k, v in labels if k.lower() == 'y']
        if xs and len(xs) == len(ys):
            return [Point(x, y) for x, y in zip(xs, ys)]

    # 无标签（或标签不完整）：按数字顺序两两配对
    numbers = [_to_float(n) for n in _NUMBER.findall(text)]
    if len(numbers) >= 2 and len(numbers) % 2 == 0:
        return [Point(numbers[i], numbers[i + 1]) for i in range(0, len(numbers), 2)]
    return []


def parse_coordinates(text: str) -> Point | None:
    """解析单个坐标点，无法解析出恰好一个点时返回 None。"""
    points = extract_points(text)
    return points[0] if len(points) == 1 else None


def parse_weapon_and_points(text: str) -> tuple[Weapon | None, list[Point]]:
    """从命令文本中解析武器与坐标点。

    首个词（或整串）能匹配到武器别名时识别为武器，其余部分解析坐标。
    返回 (weapon, points)，武器无法识别时 weapon 为 None。
    """
    text = (text or '').strip()
    weapon: Weapon | None = None
    rest = text

    if text:
        first, _, tail = text.partition(' ')
        candidate = registry.resolve(first)
        if candidate is not None:
            weapon = candidate
            rest = tail
        else:
            whole = registry.resolve(text)
            if whole is not None:
                weapon = whole
                rest = ''

    points = extract_points(rest) if rest else []
    return weapon, points


# 锁定相关保留字
_LOCK_WORD = '锁定'
_UNLOCK_WORD = '解锁'
_SHOW_WORDS = ('查看锁定', '锁定状态')


@dataclass
class ParsedCommand:
    """命令解析结果。

    action 取值：
    - 'calc'：常规计算（携带武器与坐标点）
    - 'lock'：锁定炮位（points 恰为一个坐标点）
    - 'unlock'：解除锁定
    - 'show'：查看当前锁定
    """

    action: str
    weapon: Weapon | None
    points: list[Point]


def parse_command(text: str) -> ParsedCommand:
    """解析命令文本为动作、武器与坐标点。

    优先级：
    1. '解锁' 开头 -> unlock
    2. '锁定' 开头：带坐标 -> lock；不带坐标 -> show（查看当前锁定）
    3. '查看锁定' / '锁定状态' 开头 -> show
    4. 其余 -> calc
    """
    text = (text or '').strip()

    if text.startswith(_UNLOCK_WORD):
        return ParsedCommand('unlock', None, [])

    if text.startswith(_LOCK_WORD):
        rest = text[len(_LOCK_WORD):].strip()
        points = extract_points(rest) if rest else []
        if points:
            return ParsedCommand('lock', None, points)
        return ParsedCommand('show', None, [])

    for word in _SHOW_WORDS:
        if text.startswith(word):
            return ParsedCommand('show', None, [])

    weapon, points = parse_weapon_and_points(text)
    return ParsedCommand('calc', weapon, points)


def calculate(weapon: Weapon, origin: Point, target: Point,
              origin_locked: bool = False) -> FireSolution:
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
        origin_locked=origin_locked,
    )
