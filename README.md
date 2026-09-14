# warDogsCalculatorYui

YuiChyanBot 的 WARDOGS 火炮射击诸元计算插件。

在群聊中通过对话输入炮位与目标坐标，即可算出**距离、方位角、MIL 仰角、ΔX/ΔY**，
并以结果卡片图片的形式返回，支持 **L81 迫击炮**与 **SPH-2 自行火炮**。

计算逻辑移植自开源项目 [apollyon-sys/wardogs-calculator](https://github.com/apollyon-sys/wardogs-calculator)，
弹道插值算法与原始 JavaScript 实现保持一致。

## 使用

| 命令 | 说明 |
|:-----|:-----|
| `火力计算 迫击炮 105 115 110 120` | 一条命令算出射击诸元（炮位X 炮位Y 目标X 目标Y） |
| `火力计算 迫击炮` | 缺参引导，按提示依次补全炮位与目标坐标 |
| `火力计算` | 使用默认武器（L81 迫击炮）进入引导 |
| `火力计算帮助` | 查看帮助图片 |

武器别名：

- L81 迫击炮：`迫击炮` / `l81` / `mortar`
- SPH-2 自行火炮：`榴弹炮` / `自行火炮` / `sph2` / `spg`

## 计算说明

- 坐标换算：1 游戏坐标 = 100 米。
- 距离：`hypot(ΔX, ΔY) × 100` 米。
- 方位角：正北为 0°，顺时针增大（90° 为正东）。
- 仰角：按距离对弹道表线性插值；L81 为单一解，SPH-2 在可用距离给出低角 / 高角双解。
- 射程判定：L81 为 132–684 m，SPH-2 为 780–2629 m，越界时标注"超出射程"。

## 目录结构

```
├── __init__.py           # Service 定义、触发器、缺参引导会话
├── ballistics.py         # 弹道表加载与 MIL 插值
├── calculator.py         # 坐标解析、距离/方位角/ΔXΔY 计算
├── render.py             # 结果卡片渲染（Playwright），含文本降级
├── weapons.json          # 武器与弹道数据
├── template/result.html  # 结果卡片模板
├── HELP.md               # 帮助文档（框架自动生成帮助图）
└── tests/                # 测试与数据生成脚本
```

## 测试

```bash
# 计算核心交叉验证（与参考项目原始 JS 函数比对）+ 逻辑单测
python tests/test_calculator.py

# 结果卡片渲染冒烟测试（需 Playwright 浏览器）
python tests/test_render.py

# 端到端往返测试（需先启动 BOT）
python tests/e2e_client.py
```

## 注册

在 `yuiChyan/config/extra_plugins.json5` 中启用：

```json5
{
    "warDogsCalculatorYui": "战争猎犬火力计算器",
}
```

## 许可

本项目代码以 MIT 许可发布，见 [LICENSE](LICENSE)。
WARDOGS 相关的游戏数据与素材版权归其各自所有者所有。
