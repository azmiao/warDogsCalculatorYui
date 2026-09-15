"""warDogsCalculatorYui - WARDOGS 火炮射击诸元计算。

通过一条命令完成火炮位置计算，输出距离、方位角、MIL 仰角、ΔX/ΔY 与射程判定。

用法：
- 火力计算 迫击炮 105 115 110 120
- 火力计算 105 115 110 120   （省略武器时默认 L81 迫击炮）
"""
from yuiChyan import CQEvent, YuiChyan
from yuiChyan.exception import CommandErrorException
from yuiChyan.service import Service

from .ballistics import registry
from .calculator import Point, calculate, parse_weapon_and_numbers
from .render import format_solution_text, render_solution_cq

sv = Service('warDogsCalculatorYui', help_cmd='火力计算帮助')

# 触发前缀（最长前缀匹配，'火力计算帮助' 会被 help_cmd 单独消费）
TRIGGERS = ('火力计算', '火炮计算')

_WEAPON_HINT = '、'.join(registry.all_names())

_USAGE = (
    '命令格式：火力计算 [武器] 炮位X 炮位Y 目标X 目标Y\n'
    f'例如：火力计算 105 115 110 120（省略武器默认 {registry.default.name}）\n'
    f'可用武器：{_WEAPON_HINT}'
)


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
    weapon, numbers = parse_weapon_and_numbers(text)

    # 未指定武器时默认使用 L81 迫击炮
    if weapon is None:
        weapon = registry.default

    if len(numbers) != 4:
        raise CommandErrorException(ev, _USAGE)

    origin = Point(numbers[0], numbers[1])
    target = Point(numbers[2], numbers[3])
    await _send_solution(bot, ev, weapon, origin, target)
