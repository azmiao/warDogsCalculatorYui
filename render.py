"""射击诸元结果卡片渲染。

使用框架全局 Playwright 浏览器将结果模板渲染为 PNG 图片；
浏览器不可用或渲染异常时由调用方降级为纯文本。
"""
import base64
import os
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from yuiChyan.resources import font_path, get_browser

from .calculator import FireSolution

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template')

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(['html']),
)

# 射程内用青绿，超范围用暖红
_ACCENT = '#5fd0c6'
_OUT_ACCENT = '#e08a6a'


@lru_cache(maxsize=1)
def _get_font_data_url() -> str:
    """本地中文字体转 data URL（set_content 下 file:// 不可靠，直接内嵌）。"""
    with open(font_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    return f'data:font/truetype;base64,{b64}'


def _signed(value: float) -> str:
    """带符号的米数文本，如 '+120 m' / '-80 m'。"""
    sign = '+' if value >= 0 else '-'
    return f'{sign}{round(abs(value))} m'


def _build_context(sol: FireSolution) -> dict:
    accent = _ACCENT if sol.in_range else _OUT_ACCENT
    return {
        'font_url': _get_font_data_url(),
        'accent': accent,
        'range_color': '#82c596',
        'weapon_name': sol.weapon.name,
        'in_range': sol.in_range,
        'distance_m': round(sol.distance_m),
        'distance_km': f'{sol.distance_km:.2f}',
        'azimuth': f'{sol.azimuth:.1f}',
        'mil_text': sol.mil_text,
        'mil_detail': sol.mil_detail,
        'dx_text': _signed(sol.dx_m),
        'dy_text': _signed(sol.dy_m),
        'origin_x': f'{sol.origin.x:g}',
        'origin_y': f'{sol.origin.y:g}',
        'target_x': f'{sol.target.x:g}',
        'target_y': f'{sol.target.y:g}',
        'range_text': f'{round(sol.min_range_m)}–{round(sol.max_range_m)} m',
    }


async def render_solution_image(sol: FireSolution) -> bytes | None:
    """渲染结果卡片为 PNG 字节，失败时返回 None。"""
    html = _env.get_template('result.html').render(**_build_context(sol))

    browser = get_browser()
    page = await browser.new_page(viewport={'width': 760, 'height': 480})
    try:
        await page.set_content(html, wait_until='networkidle')
        card = await page.query_selector('.card')
        if card is None:
            return None
        return await card.screenshot(type='png')
    finally:
        await page.close()


async def render_solution_cq(sol: FireSolution) -> str | None:
    """渲染结果卡片并封装为 CQ 图片消息段，失败时返回 None。"""
    img_bytes = await render_solution_image(sol)
    if not img_bytes:
        return None
    b64 = base64.b64encode(img_bytes).decode('utf-8')
    return f'[CQ:image,file=base64://{b64}]'


def format_solution_text(sol: FireSolution) -> str:
    """将射击诸元格式化为纯文本，作为图片渲染失败时的降级输出。"""
    status = '射程内' if sol.in_range else '超出射程'
    lines = [
        f'【{sol.weapon.name}】射击诸元（{status}）',
        f'距离：{round(sol.distance_m)} m（{sol.distance_km:.2f} km）',
        f'方位角：{sol.azimuth:.1f}°',
        f'仰角：{sol.mil_text}' + (f'（{sol.mil_detail}）' if sol.mil_detail else ''),
        f'ΔX：{_signed(sol.dx_m)}　ΔY：{_signed(sol.dy_m)}',
        (f'炮位：X{sol.origin.x:g} · Y{sol.origin.y:g} ➤ '
         f'目标：X{sol.target.x:g} · Y{sol.target.y:g}'),
        f'有效射程：{round(sol.min_range_m)}–{round(sol.max_range_m)} m',
    ]
    return '\n'.join(lines)
