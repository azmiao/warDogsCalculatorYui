# -*- coding: utf-8 -*-
"""渲染模块的独立冒烟测试：实际启动 Playwright 生成结果卡片图片。

运行：python tests/test_render.py
产物：tests/out_*.png
"""
import asyncio
import os
import sys
import types

sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.dirname(_HERE)
_PKG_PARENT = os.path.dirname(_PKG_DIR)
_PKG_NAME = 'warDogsCalculatorYui'
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_PKG_PARENT))

# 项目根加入路径，供 render 模块导入 yuiChyan.resources
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
if _PKG_NAME not in sys.modules:
    _pkg = types.ModuleType(_PKG_NAME)
    _pkg.__path__ = [_PKG_DIR]
    sys.modules[_PKG_NAME] = _pkg

from warDogsCalculatorYui import calculator as calc
from warDogsCalculatorYui.ballistics import registry
from warDogsCalculatorYui import render as renderer


async def main():
    from yuiChyan.resources import start_browser, close_browser

    await start_browser()
    try:
        cases = [
            ('mortar_in', registry.get('mortar'), calc.Point(105, 115), calc.Point(108, 119)),
            ('spg_dual', registry.get('spg'), calc.Point(100, 100), calc.Point(115, 120)),
            ('mortar_out', registry.get('mortar'), calc.Point(0, 0), calc.Point(0, 10)),
        ]
        for name, weapon, origin, target in cases:
            sol = calc.calculate(weapon, origin, target)
            img = await renderer.render_solution_image(sol)
            assert img and len(img) > 1000, f'{name} 渲染失败'
            out_path = os.path.join(_HERE, f'out_{name}.png')
            with open(out_path, 'wb') as f:
                f.write(img)
            print(f'[OK] {name}: {len(img)} bytes -> {out_path}')
            print(renderer.format_solution_text(sol))
            print('-' * 40)
    finally:
        await close_browser()
    print('[PASS] 渲染测试通过')


if __name__ == '__main__':
    asyncio.run(main())
