"""
视图包 —— 统一导出各页 Mixin
==============================

v3.1 的视图划分（一个能力只有一个入口）：
  overview  总览     —— 指标、趋势、风险、进度
  data      数据     —— 录入、CSV 导入导出、角色使用率、社区热度
  versions  版本     —— 看板、时间线、版本详情（任务/风险/预算/使用率）
  analysis  分析     —— 版本健康度、AI 顾问、版本对比
  report    报告     —— 智能报告、周期报表、历史归档

旧版视图已废弃：dashboard.py / ai.py / plans.py（能力已并入上表）。
"""

from .overview import OverviewMixin
from .data import DataMixin
from .versions import VersionsMixin
from .analysis import AnalysisMixin
from .report import ReportMixin

__all__ = [
    "OverviewMixin",
    "DataMixin",
    "VersionsMixin",
    "AnalysisMixin",
    "ReportMixin",
]
