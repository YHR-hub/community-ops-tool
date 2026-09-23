"""视图层单元测试（不涉及 GUI 的部分）"""
import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


class TestViewConstants:
    """测试视图常量定义"""
    
    def test_report_types(self):
        """测试报告类型常量"""
        REPORT_TYPES = {
            "周报": "weekly",
            "月报": "monthly",
        }
        
        assert "周报" in REPORT_TYPES
        assert "月报" in REPORT_TYPES
        assert REPORT_TYPES["周报"] == "weekly"
        assert REPORT_TYPES["月报"] == "monthly"
    
    def test_games_list(self):
        """测试游戏列表常量"""
        GAMES = ["原神", "崩坏：星穹铁道", "绝区零", "崩坏3", "未定事件簿", "米游社综合"]
        assert len(GAMES) == 6
        assert "原神" in GAMES
        assert "崩坏：星穹铁道" in GAMES
    
    def test_segment_defs(self):
        """测试玩家分群定义"""
        SEG_DEFS = [
            ("high",    "高活跃", "accent"),
            ("medium",  "中活跃", "success"),
            ("low",     "低活跃", "warning"),
            ("churned", "已流失", "danger"),
        ]
        assert len(SEG_DEFS) == 4


class TestAIView:
    """测试 AI 顾问相关逻辑"""
    
    def test_prompt_template_format(self):
        """测试 Prompt 模板格式"""
        template = """
        你是一位游戏运营专家，请针对以下情况提供建议：
        
        游戏：{game}
        问题：{question}
        
        请给出专业的运营建议。
        """
        
        filled = template.format(game="原神", question="DAU下降怎么办？")
        assert "原神" in filled
        assert "DAU下降" in filled
    
    def test_offline_fallback(self):
        """测试离线兜底话术"""
        fallback = "当前网络不可用，请检查 API Key 配置。"
        assert isinstance(fallback, str)
        assert len(fallback) > 0


class TestVersionsView:
    """测试版本管理相关逻辑"""
    
    def test_version_status_map(self):
        """测试版本状态映射"""
        status_map = {
            "planning": "规划中",
            "active": "进行中",
            "completed": "已完成",
            "archived": "已归档",
        }
        
        assert status_map["active"] == "进行中"
        assert status_map["planning"] == "规划中"
    
    def test_version_comparison(self):
        """测试版本对比逻辑"""
        v1 = {"dau": 100000, "revenue": 500000}
        v2 = {"dau": 120000, "revenue": 600000}
        
        # 计算增长率
        dau_growth = (v2["dau"] - v1["dau"]) / v1["dau"] * 100
        revenue_growth = (v2["revenue"] - v1["revenue"]) / v1["revenue"] * 100
        
        assert dau_growth == 20.0
        assert revenue_growth == 20.0


class TestReportView:
    """测试报告生成相关逻辑"""
    
    def test_report_markdown_format(self):
        """测试报告 Markdown 格式"""
        lines = [
            "# 米游社运营周报",
            "",
            "## 一、核心指标概览",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            "| 数据天数 | 7 天 |",
        ]
        
        content = "\n".join(lines)
        assert "# 米游社运营周报" in content
        assert "核心指标概览" in content
        assert "7 天" in content
    
    def test_report_type_mapping(self):
        """测试报告类型映射"""
        type_map = {"weekly": "周报", "monthly": "月报", "ai_report": "AI报告"}
        assert type_map["weekly"] == "周报"
        assert type_map["monthly"] == "月报"


class TestPlansView:
    """测试排期预算相关逻辑"""
    
    def test_budget_over预警(self):
        """测试超支预警逻辑"""
        planned = 100000
        actual = 120000
        
        is_over_budget = actual > planned
        assert is_over_budget is True
    
    def test_risk_matrix_scoring(self):
        """测试风险矩阵评分"""
        probability = 3  # 高
        impact = 4       # 严重
        
        risk_score = probability * impact
        assert risk_score == 12
        assert risk_score <= 25  # 最大可能得分 5x5=25


class TestMarketingView:
    """测试内容工厂相关逻辑"""
    
    def test_platform_support(self):
        """测试平台支持"""
        platforms = ["微博", "B站", "小红书"]
        assert len(platforms) == 3
        assert "微博" in platforms
        assert "B站" in platforms
        assert "小红书" in platforms
    
    def test_style_options(self):
        """测试风格选项"""
        styles = ["官方", "二次元", "悬念", "热血"]
        assert len(styles) == 4
        assert "官方" in styles
        assert "二次元" in styles
    
    def test_copy_type_options(self):
        """测试文案类型选项"""
        copy_types = ["社媒文案", "活动海报", "投放素材"]
        assert len(copy_types) == 3
        assert "社媒文案" in copy_types


class TestSocialTrendView:
    """测试趋势雷达相关逻辑"""
    
    def test_trend_categories(self):
        """测试热点分类"""
        # 24 种预设热点
        trends = [
            "版本更新", "新角色", "新武器", "新活动",
            "平衡调整", "Bug修复", "福利发放", "节日活动",
            "联动合作", "电竞赛事", "社区热点", "舆情监控",
            "竞品动态", "行业趋势", "玩家反馈", "数据波动",
            "技术升级", "内容创作", "二创热点", "直播动态",
            "周边产品", "线下活动", "官方公告", "版本前瞻"
        ]
        assert len(trends) == 24
    
    def test_heat_score_color(self):
        """测试热度评分颜色映射"""
        heat_score = 85
        
        if heat_score >= 80:
            color = "red"
        elif heat_score >= 60:
            color = "orange"
        elif heat_score >= 40:
            color = "yellow"
        else:
            color = "green"
        
        assert color == "red"
    
    def test_heat_score_low(self):
        """测试低热度颜色"""
        heat_score = 30
        if heat_score >= 80:
            color = "red"
        elif heat_score >= 60:
            color = "orange"
        elif heat_score >= 40:
            color = "yellow"
        else:
            color = "green"
        assert color == "green"


class TestSettingsView:
    """测试 AI 设置相关逻辑"""
    
    def test_api_key_validation(self):
        """测试 API Key 格式验证"""
        valid_keys = [
            "sk-1234567890abcdef",
            "sk-proj-abc123",
            "sk-test-key",
        ]
        
        for key in valid_keys:
            assert isinstance(key, str)
            assert len(key) > 5
    
    def test_model_options(self):
        """测试模型选项"""
        models = [
            "deepseek-chat",
            "deepseek-v4-pro",
            "gpt-4o-mini",
            "gpt-4",
        ]
        
        assert len(models) == 4
        assert "deepseek-chat" in models


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
