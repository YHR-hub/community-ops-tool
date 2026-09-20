# -*- coding: utf-8 -*-
"""
结构化日志 —— 让真实使用中的问题可追溯
======================================

为什么需要：
  工具的界面反馈是 toast，一闪而过；出错时用户只能截图描述「刚才弹了个红条」。
  没有日志的话，定位问题全靠复现 —— 而桌面应用最难的就是复现。

设计取舍：
  · 只落文件，不做远程上报（工具是本地单机，个人数据不上网是底线）；
  · 滚动文件（单个 1MB × 3 份），不无限增长占用户磁盘；
  · frozen（打包后）时落到 exe 旁的 logs/，而不是临时解包目录
    （与 db._db_path() 同样的坑：onefile 的 __file__ 指向临时目录）；
  · 控制台在 --noconsole 打包下不存在，所以只配 FileHandler。
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_NAME = "ops_tool"
_MAX_BYTES = 1024 * 1024      # 单文件 1MB
_BACKUP_COUNT = 3


def log_dir():
    """日志目录：frozen 时落在 exe 旁，源码运行时落在项目下。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "logs")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        # 极端情况（只读目录）：退回临时目录，日志不是主流程，不能让它拖垮启动
        path = os.path.join(os.path.expanduser("~"), ".ops_tool_logs")
        os.makedirs(path, exist_ok=True)
    return path


def setup_logging(level=logging.INFO):
    """初始化日志，返回 logger。重复调用不会重复挂 handler。"""
    logger = logging.getLogger(LOG_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%m-%d %H:%M:%S")
    try:
        fh = RotatingFileHandler(
            os.path.join(log_dir(), "ops_tool.log"),
            maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
            encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:      # 日志初始化失败不应阻断启动
        print(f"日志初始化失败：{e}")
    return logger


def get_logger():
    return logging.getLogger(LOG_NAME)


def log_event(action, detail=""):
    """业务动作留痕（对应 activity_log 表的兄弟：一个是业务视角，一个是运维视角）。"""
    get_logger().info("%s %s", action, detail or "")
