"""炮位坐标锁定存储。

按用户维度持久化保存锁定的炮位坐标（跨群通用），底层复用框架 rocksdict
数据库目录，进程退出时自动释放句柄。

RocksDB 同一路径在同一进程内只允许打开一个实例，因此这里维护模块级单例，
避免并发重复打开触发文件锁错误。
"""
import atexit
import contextlib
import json
import os

from rocksdict import Rdict

from yuiChyan.resources import base_db_path

from .calculator import Point

_DB_PATH = os.path.join(base_db_path, 'war_dogs_lock.db')

_db: Rdict | None = None


def _close_db() -> None:
    """进程退出时释放数据库句柄。"""
    global _db
    if _db is not None:
        with contextlib.suppress(Exception):
            _db.close()
        _db = None


def _get_db() -> Rdict:
    """懒加载单例数据库，避免重复打开导致的文件锁冲突。"""
    global _db
    if _db is None:
        _db = Rdict(_DB_PATH)
        atexit.register(_close_db)
    return _db


def _key(user_id: int | str) -> str:
    return str(user_id)


def get_lock(user_id: int | str) -> Point | None:
    """获取用户锁定的炮位坐标，未锁定或数据损坏时返回 None。"""
    raw = _get_db().get(_key(user_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return Point(float(data['x']), float(data['y']))
    except (ValueError, KeyError, TypeError):
        return None


def set_lock(user_id: int | str, point: Point) -> None:
    """锁定（或替换）用户的炮位坐标。"""
    _get_db()[_key(user_id)] = json.dumps({'x': point.x, 'y': point.y})


def clear_lock(user_id: int | str) -> bool:
    """解除用户锁定，返回原本是否存在锁定。"""
    db = _get_db()
    if db.get(_key(user_id)) is None:
        return False
    db.delete(_key(user_id))
    return True
