/*
 * 基准值生成器：直接加载参考项目原始的 weapons.js 纯函数，
 * 对采样距离计算 MIL 仰角解，输出 JSON 供 Python 侧交叉验证。
 *
 * 用法：node gen_reference.js
 */
const fs = require('fs');
const path = require('path');

const refSource = fs.readFileSync(path.join(__dirname, 'ref_weapons.js'), 'utf8');

// 参考文件中的纯函数定义在顶层，直接在同一作用域求值即可调用
// eslint-disable-next-line no-eval
eval(refSource);

const weaponsData = JSON.parse(
    fs.readFileSync(path.join(__dirname, '..', 'weapons.json'), 'utf8')
);

const weapons = {};
weaponsData.weapons.forEach(item => {
    weapons[item.id] = normalizeWeapon(item);
});

// 采样距离：覆盖射程内外、弹道表端点与中间值
const samples = {
    mortar: [80, 132, 150, 200, 300, 400, 500, 600, 684, 700, 50, 1000],
    spg: [700, 780, 1000, 1500, 2000, 2400, 2629, 2700, 500, 3000]
};

const out = {};
Object.keys(weapons).forEach(id => {
    out[id] = {};
    samples[id].forEach(d => {
        const sol = getWeaponElevationSolutions(weapons[id], d);
        out[id][String(d)] = {
            inRange: sol.inRange,
            single: sol.single,
            low: sol.low,
            high: sol.high
        };
    });
});

process.stdout.write(JSON.stringify(out, null, 2));
