# 危险信号必须优先用规则判断，不能直接用llm判断，避免误判导致漏诊。
# 规则判断后可以用llm进行补充说明和建议，但不能作为唯一

# 识别用户输入中是否存在紧急就医风险
# 后续优化：这个匹配太简单了，可以考虑引入更复杂的规则引擎，或者使用专门的医疗文本分类模型来辅助判断。

from app.models.schemas import RiskResult


class RiskService:
    """
    危险信号识别服务
    ================
    职责：
    1. 根据用户症状判断风险等级
    2. 识别是否存在高危症状
    3. 给出就医建议

    注意：
    本模块只做规则判断，不做医学诊断。
    """
    HIGH_RISK_KEYWORDS = {
        "胸痛": "胸痛可能与心血管急症相关，建议尽快就医。",
        "呼吸困难": "呼吸困难属于高风险症状，建议尽快就医。",
        "意识模糊": "意识模糊属于高风险信号，建议立即就医。",
        "昏迷": "昏迷属于紧急情况，建议立即联系急救服务。",
        "抽搐": "抽搐属于高风险症状，建议尽快就医。",
        "大量出血": "大量出血需要立即处理。",
        "突发剧烈头痛": "突发剧烈头痛需要警惕严重神经系统问题。",
        "肢体无力": "肢体无力需要警惕神经系统急症。",
        "说话不清": "说话不清可能提示神经系统急症，建议尽快就医。",
        "持续高热": "持续高热可能存在感染等风险，建议及时就医。",
        "便血": "便血可能提示消化道出血等问题，建议及时就医。",
        "呕血": "呕血属于高风险症状，建议立即就医。"
    }

    MEDIUM_RISK_KEYWORDS = {
        "反复头痛": "反复头痛建议尽快到神经内科或全科医学科就诊。",
        "长期失眠": "长期失眠可能影响身心健康，建议就诊评估。",
        "持续咳嗽": "持续咳嗽建议到呼吸内科或全科医学科就诊。",
        "体重下降": "不明原因体重下降建议进一步检查。",
        "食欲下降": "长期食欲下降建议就医评估。",
        "乏力": "长期乏力可能与多种因素有关，建议进一步检查。",
        "头晕": "反复头晕建议就诊评估。"
    }

    LONG_DURATION_KEYWORDS = [
        "一周",
        "两周",
        "三周",
        "一个月",
        "两个月",
        "半年",
        "长期",
        "反复",
        "持续"
    ]
    
    def detect_risk(self, 
                    symptoms: str,
                    duration: str = None) -> RiskResult:
        """根据症状和持续时间判断风险等级"""
        symptoms_text = symptoms or "" 
        duration_text = duration or "" 
        
        full_text = symptoms_text + " " + duration_text 
        
        warnings = [] 
        
        # 1. 检查高风险关键词
        for keyword, warning in self.HIGH_RISK_KEYWORDS.items():
            if keyword in full_text:
                warnings.append(warning)
        
        if warnings:
            return RiskResult(
                risk_level="HIGH",
                warnings=warnings,
                action="建议立即就医，或联系急救服务。"
            )  
        
        # 2. 检查中风险关键词
        for keyword, warning in self.MEDIUM_RISK_KEYWORDS.items():
            if keyword in full_text:
                warnings.append(warning)
        
        # 3. 持续时间较长提升为中风险
        has_long_duration = any(
            keyword in full_text for keyword in self.LONG_DURATION_KEYWORDS
        )
        
        if warnings or has_long_duration:
            if not warnings:
                warnings.append("症状持续时间较长，建议就医评估。")
            return RiskResult(
                risk_level="MEDIUM",
                warnings=warnings,
                action="建议尽快就医，进行详细评估。"
            ) 
            
        # 4. 其他情况视为低风险
        return RiskResult(
            risk_level="LOW",
            warnings=[],
            action="症状较轻，建议观察并注意休息。如症状加重，请及时就医。"
        )                             



