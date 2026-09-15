"""端到端测试客户端：模拟 OneBot 反向 WS 客户端，保持连接完成一次完整往返。

需先启动 BOT（runYuiChyan.py），再运行本脚本。
用法：python tests/e2e_client.py
"""
import asyncio
import json
import random
import sys
import time

import websockets

sys.stdout.reconfigure(encoding='utf-8')

BOT_ID = 233333333
SENDER_ID = 2362020227
GROUP_ID = 66666666
WS_URL = 'ws://127.0.0.1:2333/ws/'
ACCESS_TOKEN = 'test'

# 待发送的测试消息序列
MESSAGES = [
    '火力计算 迫击炮 105 115 110 120',
    '火力计算 榴弹炮 100 100 115 120',
    '火力计算 迫击炮',
    '105 115',
    '110 120',
    '火力计算帮助',
]

# 每条消息之间的等待时间（秒），给渲染留足时间
STEP_INTERVAL = 6


def _describe(message) -> str:
    """将 bot 回复的 message 描述为可读摘要。"""
    if isinstance(message, str):
        return message
    parts = []
    for seg in message:
        if isinstance(seg, dict):
            stype = seg.get('type')
            data = seg.get('data', {})
            if stype == 'text':
                parts.append(data.get('text', ''))
            elif stype == 'image':
                f = str(data.get('file', ''))
                if f.startswith('base64://'):
                    parts.append(f'[图片 base64 长度={len(f) - 9}]')
                else:
                    parts.append(f'[图片 {f[:40]}]')
            else:
                parts.append(f'[{stype}]')
        else:
            parts.append(str(seg))
    return ''.join(parts).strip()


async def receive_loop(ws, collected: list):
    async def respond(action: str, params: dict):
        echo = params.pop('__echo__', None)
        if action == 'get_group_list':
            data = [{'group_id': GROUP_ID, 'group_name': '测试群',
                     'member_count': 10, 'max_member_count': 500}]
        elif action == 'get_group_member_info':
            data = {'group_id': GROUP_ID, 'user_id': SENDER_ID,
                    'nickname': 'AZMIAO', 'sex': 'male', 'age': 0, 'role': 'owner'}
        else:
            data = {'message_id': random.randint(10000000, 99999999)}
        await ws.send(json.dumps({'echo': echo, 'data': data, 'retcode': 0,
                                  'status': 'ok', 'message': ''}))

    while True:
        raw = await ws.recv()
        payload = json.loads(raw)
        action = payload.get('action', '')
        params = payload.get('params', {}) or {}
        echo = payload.get('echo')
        if action in ('send_msg', 'send_group_msg', 'send_private_msg'):
            collected.append(_describe(params.get('message', '')))
        params['__echo__'] = echo
        await respond(action, params)


async def main():
    collected: list[str] = []
    async with websockets.connect(
        WS_URL,
        additional_headers={
            'X-Self-ID': str(BOT_ID),
            'X-Client-Role': 'Universal',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + ACCESS_TOKEN,
        },
        max_size=2 ** 20 * 20,
    ) as ws:
        print(f'> 已连接至 {WS_URL}')
        recv_task = asyncio.create_task(receive_loop(ws, collected))

        for i, text in enumerate(MESSAGES):
            await asyncio.sleep(STEP_INTERVAL if i else 1)
            msg_id = random.randint(10000000, 99999999)
            data = {
                'time': int(time.time()),
                'self_id': BOT_ID,
                'post_type': 'message',
                'sub_type': 'normal',
                'message_id': msg_id,
                'user_id': SENDER_ID,
                'message_type': 'group',
                'detail_type': 'group',
                'group_id': GROUP_ID,
                'raw_message': text,
                'message': text,
                'sender': {'card': 'AZMIAO', 'nickname': 'AZMIAO'},
            }
            await ws.send(json.dumps(data))
            print(f'\n>>> 发送: {text}')
            await asyncio.sleep(2)
            if collected:
                for reply in collected:
                    print(f'<<< 回复: {reply}')
                collected.clear()

        await asyncio.sleep(3)
        recv_task.cancel()

    print('\n[PASS] 端到端往返测试完成')


if __name__ == '__main__':
    asyncio.run(main())
