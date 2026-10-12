"""Deterministic first-pass triage.

The LLM is deliberately not allowed to lower this result.  This module does
not diagnose disease; it only spots explicit urgency signals and understands
common Chinese negation patterns.
"""

import re

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
    IMMEDIATE_SIGNALS = {
        "意识模糊": "出现意识模糊，需要立即由急诊评估。",
        "昏迷": "出现昏迷，请立即联系急救服务。",
        "抽搐": "出现抽搐，需要尽快由急诊评估。",
        "大量出血": "出现大量出血，请立即联系急救服务。",
        "呕血": "出现呕血，需要立即由急诊评估。",
        "黑便": "出现黑便并伴明显不适，需要尽快由急诊评估。",
        "突发剧烈头痛": "突发剧烈头痛属于需要尽快排查的危险信号。",
        "肢体无力": "新发肢体无力需要尽快排查神经系统急症。",
        "一侧无力": "新发一侧肢体无力需要尽快排查神经系统急症。",
        "说话不清": "新发说话不清需要尽快排查神经系统急症。",
        "呼吸困难": "出现呼吸困难，需要尽快由急诊评估。",
    }

    CHEST_PAIN_COMPANIONS = ("大汗", "冷汗", "呼吸困难", "胸闷", "左肩", "下颌", "濒死感")

    NEGATION_PATTERNS = (
        r"没有(?:出现)?$", r"无$", r"未见$", r"否认$", r"并无$",
        r"不伴$", r"没有明显$", r"未出现$", r"未发生$",
    )

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
    
    @classmethod
    def _signal_state(cls, text: str, signal: str) -> tuple[bool, bool]:
        """Return (affirmed, negated) across every occurrence of a signal."""
        affirmed = False
        negated = False
        for match in re.finditer(re.escape(signal), text):
            prefix = text[max(0, match.start() - 8):match.start()].replace(" ", "")
            # Chinese often applies one negation to a coordinated list, e.g.
            # "没有胸痛、呼吸困难和肢体无力". Keep the whole comma-delimited
            # clause so the negation reaches every listed signal.
            clause_prefix = re.split(r"[，,。.!！？?；;]", text[:match.start()])[-1].replace(" ", "")[-32:]
            has_direct_negation = any(re.search(pattern, prefix) for pattern in cls.NEGATION_PATTERNS)
            negation = re.search(r"(?:没有(?:出现|明显)?|无明显|无|未见|否认|并无|不伴|未出现|未发生)", clause_prefix)
            has_reversal = bool(
                negation and re.search(r"(?:但|不过|然而|可是|后来|现在)", clause_prefix[negation.end():])
            )
            is_negated = has_direct_negation or bool(negation and not has_reversal)
            if is_negated:
                negated = True
            else:
                affirmed = True
        return affirmed, negated

    @classmethod
    def _present(cls, text: str, signal: str) -> bool:
        return cls._signal_state(text, signal)[0]

    def detect_risk(self, symptoms: str, duration: str | None = None) -> RiskResult:
        """Assess urgency from explicit text while preserving negated findings."""
        full_text = f"{symptoms or ''} {duration or ''}".strip()
        warnings: list[str] = []
        matched: list[str] = []
        negated: list[str] = []

        all_signals = set(self.IMMEDIATE_SIGNALS) | set(self.MEDIUM_RISK_KEYWORDS) | {"胸痛"}
        for signal in all_signals:
            affirmed, is_negated = self._signal_state(full_text, signal)
            if is_negated and not affirmed:
                negated.append(signal)

        for signal, warning in self.IMMEDIATE_SIGNALS.items():
            if self._present(full_text, signal):
                matched.append(signal)
                warnings.append(warning)

        chest_pain = self._present(full_text, "胸痛")
        chest_companions = [item for item in self.CHEST_PAIN_COMPANIONS if self._present(full_text, item)]
        if chest_pain and chest_companions:
            matched.extend(["胸痛", *chest_companions])
            warnings.append("胸痛同时伴有其他危险表现，需要立即由急诊评估。")

        if warnings:
            return RiskResult(
                risk_level="HIGH",
                warnings=list(dict.fromkeys(warnings)),
                action="请尽快前往急诊；如果症状正在发生、明显加重或无法安全自行前往，请联系 120。",
                matched_signals=list(dict.fromkeys(matched)),
                negated_signals=sorted(negated),
            )
        
        # 2. 检查中风险关键词
        for keyword, warning in self.MEDIUM_RISK_KEYWORDS.items():
            if self._present(full_text, keyword):
                matched.append(keyword)
                warnings.append(warning)

        if chest_pain:
            matched.append("胸痛")
            warnings.append("胸痛即使没有其他危险表现，也建议尽快线下评估；若加重或出现呼吸困难、大汗，请立即就医。")
        
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
                action="建议近期安排线下就诊；如果症状加重或出现新的危险信号，请改去急诊。",
                matched_signals=list(dict.fromkeys(matched)),
                negated_signals=sorted(negated),
            )
            
        # 4. 其他情况视为低风险
        return RiskResult(
            risk_level="LOW",
            warnings=[],
            action="目前描述中未识别到明确急症信号。可以留意变化并按建议就诊；若症状加重，请及时线下就医。",
            matched_signals=[],
            negated_signals=sorted(negated),
        )



