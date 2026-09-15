"""warDogsCalculatorYui - WARDOGS 火炮射击诸元计算。

通过对话完成火炮位置计算，输出距离、方位角、MIL 仰角、ΔX/ΔY 与射程判定。

交互：
- 一条命令完成：火力计算 迫击炮 105 115 110 120
- 缺参引导：只发 '火力计算 迫击炮' 后，按提示依次补全炮位与目标坐标
"""
import time

from yuiChyan import CQEvent, YuiChyan
from yuiChyan.exception import CommandErrorException
from yuiChyan.service import Service

from .ballistics import registry
from .calculator import Point, calculate, extract_numbers, parse_weapon_and_numbers
from .render import format_solution_text, render_solution_cq

sv = Service('warDogsCalculatorYui', help_cmd='火力计算帮助')

# 触发前缀（最长前缀匹配，'火力计算帮助' 会被 help_cmd 单独消费）
TRIGGERS = ('火力计算', '火炮计算')

# 会话有效期（秒），超时自动失效
SESSION_TTL = 180

# 待补全会话：key=(group_id, user_id) -> {'weapon': Weapon, 'origin': Point, 'step': str, 'time': float}
_sessions: dict[tuple[int, int], dict] = {}

_WEAPON_HINT = '、'.join(registry.all_names())


def _cleanup_sessions():
    """清理超时会话。"""
    now = time.time()
    for key in list(_sessions.keys()):
        if now - _sessions[key]['time'] > SESSION_TTL:
            _sessions.pop(key, None)


async def _send_solution(bot: YuiChyan, ev: CQEvent, weapon, origin: Point, target: Point):
    """计算并发送射击诸元结果（图片，失败时降级为文本）。"""
    solution = calculate(weapon, origin, target)
    try:
        image_cq = await render_solution_cq(solution)
    except Exception as e:
        # 兜底降级：渲染依赖浏览器/模板/字体，任何异常都不应阻断业务，统一回退为文本
        sv.logger.error(f'结果图片渲染失败，降级为文本输出：{type(e)} {e}')
        image_cq = None
    await bot.send(ev, image_cq or format_solution_text(solution))


@sv.on_prefix(TRIGGERS)
async def fire_calc(bot: YuiChyan, ev: CQEvent):
    # 前缀已被剥离，ev.message 为剩余文本
    text = str(ev.message).strip()
    _cleanup_sessions()
    key = (int(ev.group_id), int(ev.user_id))

    weapon, numbers = parse_weapon_and_numbers(text)

    # 四个数字：炮位X 炮位Y 目标X 目标Y，一次算完
    if len(numbers) == 4:
        if weapon is None:
            weapon = registry.default
        origin = Point(numbers[0], numbers[1])
        target = Point(numbers[2], numbers[3])
        _sessions.pop(key, None)
        await _send_solution(bot, ev, weapon, origin, target)
        return

    # 参数不完整，进入引导会话
    if weapon is None:
        weapon = registry.default

    if len(numbers) == 2:
        # 已给炮位，等待目标
        _sessions[key] = {
            'weapon': weapon,
            'origin': Point(numbers[0], numbers[1]),
            'step': 'target',
            'time': time.time(),
        }
        await bot.send(ev, f'> 已选择【{weapon.name}】，炮位 X{numbers[0]:g} Y{numbers[1]:g}\n'
                           f'请发送目标坐标，例如：110 120')
        return

    if len(numbers) not in (0, 2):
        raise CommandErrorException(
            ev, '坐标数量不正确，请提供 4 个数字（炮位X 炮位Y 目标X 目标Y），'
                '例如：火力计算 迫击炮 105 115 110 120',
        )

    # 无坐标，等待炮位
    _sessions[key] = {
        'weapon': weapon,
        'origin': None,
        'step': 'origin',
        'time': time.time(),
    }
    await bot.send(ev, f'> 已选择【{weapon.name}】\n'
                       f'请发送炮位坐标（X Y），例如：105 115\n'
                       f'可用武器：{_WEAPON_HINT}')


@sv.on_message('group')
async def session_input(bot: YuiChyan, ev: CQEvent):
    """消费引导会话中的纯坐标回复。

    仅当该用户存在有效会话且消息能解析为坐标时处理，否则不响应。
    """
    _cleanup_sessions()
    key = (int(ev.group_id), int(ev.user_id))
    session = _sessions.get(key)
    if not session:
        return

    text = str(ev.message).strip()
    numbers = extract_numbers(text)
    if len(numbers) != 2:
        return

    point = Point(numbers[0], numbers[1])

    if session['step'] == 'origin':
        session['origin'] = point
        session['step'] = 'target'
        session['time'] = time.time()
        await bot.send(ev, f'> 炮位已设为 X{point.x:g} Y{point.y:g}\n'
                           f'请发送目标坐标，例如：110 120')
        return

    if session['step'] == 'target':
        origin = session['origin']
        weapon = session['weapon']
        _sessions.pop(key, None)
        await _send_solution(bot, ev, weapon, origin, point)
