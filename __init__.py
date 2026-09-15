"""warDogsCalculatorYui - 战狗(WARDOGS)火炮射击诸元计算。

通过一条命令完成火炮位置计算，输出距离、方位角、MIL 仰角、ΔX/ΔY 与射程判定。

用法：
- 火力计算 迫击炮 105 115 110 120
- 火力计算 105 115 110 120   （省略武器时默认 L81 迫击炮）
- 火力计算 x97.43, y109.27 x100.5, y120.3   （支持带 x/y 标签的坐标）
- 火力计算 锁定 105 115   （锁定炮位坐标，之后只需输入目标坐标）
- 火力计算 解锁          （解除锁定）
"""
from yuiChyan import CQEvent, YuiChyan
from yuiChyan.exception import CommandErrorException
from yuiChyan.service import Service

from . import store
from .ballistics import registry
from .calculator import Point, calculate, parse_command
from .render import format_solution_text, render_solution_cq

sv = Service('warDogsCalculatorYui', help_cmd='火力计算帮助')

# 触发前缀（最长前缀匹配，'火力计算帮助' 会被 help_cmd 单独消费）
TRIGGERS = ('火力计算', '火炮计算', 'hljs')

_WEAPON_HINT = '、'.join(registry.all_names())

_USAGE = (
    '命令格式：火力计算 [武器] 炮位坐标 目标坐标\n'
    f'例如：火力计算 105 115 110 120（省略武器默认 {registry.default.name}）\n'
    '也支持：火力计算 x97.43, y109.27 x100.5, y120.3\n'
    '锁定炮位：火力计算 锁定 105 115，之后只需 火力计算 目标坐标\n'
    f'可用武器：{_WEAPON_HINT}'
)

_LOCK_USAGE = (
    '命令格式：火力计算 锁定 炮位坐标\n'
    '例如：火力计算 锁定 105 115 或 火力计算 锁定 x97.43, y109.27\n'
    '锁定后只需输入目标坐标即可计算：火力计算 110 120'
)


async def _send_solution(bot: YuiChyan, ev: CQEvent, weapon, origin: Point,
                         target: Point, origin_locked: bool = False):
    """计算并发送射击诸元结果（图片，失败时降级为文本）。"""
    solution = calculate(weapon, origin, target, origin_locked=origin_locked)
    try:
        image_cq = await render_solution_cq(solution)
    except Exception as e:
        # 兜底降级：渲染依赖浏览器/模板/字体，任何异常都不应阻断业务，统一回退为文本
        sv.logger.error(f'结果图片渲染失败，降级为文本输出：{type(e)} {e}')
        image_cq = None
    await bot.send(ev, image_cq or format_solution_text(solution))


def _fmt_point(point: Point) -> str:
    return f'X{point.x:g} · Y{point.y:g}'


async def _handle_calc(bot: YuiChyan, ev: CQEvent, weapon, points):
    """常规计算：显式两点，或单点配合已锁定的炮位。"""
    if len(points) == 2:
        origin, target = points
        await _send_solution(bot, ev, weapon, origin, target, origin_locked=False)
        return

    if len(points) == 1:
        origin = store.get_lock(ev.user_id)
        if origin is None:
            raise CommandErrorException(
                ev,
                '未检测到锁定的炮位坐标，请先用 火力计算 锁定 炮位坐标 锁定。\n' + _USAGE,
            )
        await _send_solution(bot, ev, weapon, origin, points[0], origin_locked=True)
        return

    raise CommandErrorException(ev, _USAGE)


async def _handle_lock(bot: YuiChyan, ev: CQEvent, points):
    """锁定（或替换）炮位坐标。"""
    if len(points) != 1:
        raise CommandErrorException(ev, _LOCK_USAGE)

    point = points[0]
    existed = store.get_lock(ev.user_id) is not None
    store.set_lock(ev.user_id, point)

    action = '已更新锁定' if existed else '已锁定'
    await bot.send(
        ev,
        f'🔒 炮位坐标{action}：{_fmt_point(point)}\n'
        '之后只需发送目标坐标即可计算，例如：火力计算 110 120\n'
        '更换位置后请重新锁定，或发送 火力计算 解锁 解除。',
    )


async def _handle_unlock(bot: YuiChyan, ev: CQEvent):
    """解除炮位坐标锁定。"""
    if store.clear_lock(ev.user_id):
        await bot.send(ev, '🔓 已解除炮位坐标锁定，后续计算请重新输入完整坐标。')
    else:
        await bot.send(ev, '当前没有锁定的炮位坐标，无需解锁。')


async def _handle_show(bot: YuiChyan, ev: CQEvent):
    """查看当前锁定的炮位坐标。"""
    point = store.get_lock(ev.user_id)
    if point is None:
        await bot.send(
            ev,
            '当前未锁定炮位坐标。\n'
            '发送 火力计算 锁定 炮位坐标 即可锁定，例如：火力计算 锁定 105 115',
        )
        return
    await bot.send(
        ev,
        f'🔒 当前锁定的炮位坐标：{_fmt_point(point)}\n'
        '发送 火力计算 目标坐标 即可计算，或发送 火力计算 解锁 解除锁定。',
    )


@sv.on_prefix(TRIGGERS)
async def fire_calc(bot: YuiChyan, ev: CQEvent):
    # 前缀已被剥离，ev.message 为剩余文本
    text = str(ev.message).strip()
    command = parse_command(text)

    if command.action == 'lock':
        await _handle_lock(bot, ev, command.points)
        return
    if command.action == 'unlock':
        await _handle_unlock(bot, ev)
        return
    if command.action == 'show':
        await _handle_show(bot, ev)
        return

    # 未指定武器时默认使用 L81 迫击炮
    weapon = command.weapon or registry.default
    await _handle_calc(bot, ev, weapon, command.points)
