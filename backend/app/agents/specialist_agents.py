"""Small specialist agents used by the medical team orchestrator."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from app.agents.health_agent import HealthAgentOutput
from app.config import settings
from app.models.schemas import EvidenceItem, HealthConsultRequest, RiskResult
from app.services.risk_service import RiskService


class TriageAgent:
    """Own urgency assessment so a generative model cannot silently lower it."""

    def __init__(self) -> None:
        self.service = RiskService()

    async def run(self, request: HealthConsultRequest) -> RiskResult:
        return self.service.detect_risk(request.symptoms, request.duration)


class EvidenceAgent:
    """Retrieve source excerpts and degrade to built-in guides when RAG is offline."""

    async def run(self, request: HealthConsultRequest) -> list[EvidenceItem]:
        query = " ".join(part for part in (request.symptoms, request.duration, request.goal) if part)
        return await asyncio.to_thread(self._search, query)

    def _search(self, query: str) -> list[EvidenceItem]:
        try:
            from app.rag.hybrid_retriever import HybridMedicalRetriever

            results = HybridMedicalRetriever().retrieve(query=query, final_top_k=4)
            evidence: list[EvidenceItem] = []
            for item in results:
                metadata = item.metadata or {}
                source = str(
                    metadata.get("original_file_name")
                    or metadata.get("file_name")
                    or metadata.get("source")
                    or "医学知识库"
                )
                score = item.rerank_score or item.hybrid_score
                evidence.append(
                    EvidenceItem(
                        source=Path(source).name,
                        title=str(metadata.get("title") or Path(source).stem or "医学资料"),
                        excerpt=self._clean_excerpt(item.content),
                        relevance=max(0.0, min(float(score), 1.0)),
                    )
                )
            if evidence:
                return self._deduplicate(evidence)
        except Exception as exc:
            print(f"[EvidenceAgent] 混合检索不可用，回退到内置指南: {type(exc).__name__}: {exc}")

        return self._search_builtin_guides(query)

    def _search_builtin_guides(self, query: str) -> list[EvidenceItem]:
        guide_dir = Path(settings.MEDICAL_DOCS_DIR)
        if not guide_dir.exists():
            return []

        aliases = {
            "headache": ("头痛", "头疼", "偏头痛"),
            "chest_pain": ("胸痛", "胸闷", "心口痛"),
            "cough": ("咳嗽", "咳痰"),
            "insomnia": ("失眠", "睡不着", "睡眠"),
            "anxiety": ("焦虑", "紧张", "心慌"),
            "stomach_pain": ("胃痛", "胃疼", "腹痛", "肚子痛"),
        }
        matched_stems = {
            stem
            for stem, words in aliases.items()
            if any(RiskService._present(query, word) for word in words)
        }
        evidence: list[EvidenceItem] = []
        for path in guide_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8").strip()
            if path.stem not in matched_stems:
                continue
            title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
            evidence.append(
                EvidenceItem(
                    source=path.name,
                    title=title_match.group(1).strip() if title_match else path.stem,
                    excerpt=self._clean_excerpt(text),
                    relevance=0.72,
                )
            )
        return evidence[:4]

    @staticmethod
    def _clean_excerpt(text: str) -> str:
        text = re.sub(r"#+\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:320]

    @staticmethod
    def _deduplicate(items: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[tuple[str, str]] = set()
        result: list[EvidenceItem] = []
        for item in items:
            key = (item.source, item.excerpt[:80])
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


class SafetyReviewAgent:
    """Enforce source and triage invariants after generation."""

    FORBIDDEN_PATTERNS = (
        r"你(?:已经)?患有", r"可以确诊", r"诊断为", r"一定是", r"服用\S+\d+(?:mg|毫克)",
    )

    def run(
        self,
        output: HealthAgentOutput,
        triage: RiskResult,
        evidence: list[EvidenceItem],
    ) -> tuple[HealthAgentOutput, bool, list[str]]:
        corrected = False
        limitations: list[str] = []

        if output.risk_result != triage:
            output.risk_result = triage
            corrected = True

        if not output.summary.strip():
            output.summary = "我们先把这次不舒服的关键信息整理好，再由线下医生结合检查进一步判断。"
            corrected = True

        allowed_sources = list(dict.fromkeys(item.source for item in evidence))
        if output.references != allowed_sources:
            output.references = allowed_sources
            corrected = True

        all_text = " ".join([output.summary, *output.possible_causes, *output.lifestyle_advice])
        if any(re.search(pattern, all_text) for pattern in self.FORBIDDEN_PATTERNS):
            output.possible_causes = [
                "仅凭目前信息无法判断具体原因，医生会结合面诊和必要检查逐步排查。"
            ]
            output.lifestyle_advice = ["在医生明确评估前，不要自行开始、停用或调整处方药。"]
            corrected = True
            limitations.append("生成内容触及诊断或用药边界，已替换为保守表述。")

        if not evidence:
            limitations.append("当前知识库没有检索到直接相关资料，相关因素仅作一般性说明。")
            output.possible_causes = [
                "现有资料不足以判断具体原因，建议由医生结合问诊、体格检查和必要检查进一步评估。"
            ]
            corrected = True

        if triage.risk_level == "HIGH" and output.department_result.primary_department != "急诊科":
            output.department_result.primary_department = "急诊科"
            output.department_result.alternative_departments = []
            output.department_result.reason = "存在需要尽快排查的危险信号，先由急诊评估更稳妥。"
            corrected = True

        return output, corrected, limitations


class ToneAgent:
    """Apply a narrow language pass without changing medical meaning."""

    REPLACEMENTS = {
        "该患者": "你",
        "患者应": "你可以",
        "建议患者": "建议你",
        "基于您提供的信息": "从你刚才的描述看",
        "根据您描述的症状": "从你描述的不舒服来看",
    }

    def run(self, output: HealthAgentOutput) -> HealthAgentOutput:
        def soften(value: str) -> str:
            for source, target in self.REPLACEMENTS.items():
                value = value.replace(source, target)
            return value.strip()

        output.summary = soften(output.summary)
        output.department_result.reason = soften(output.department_result.reason)
        output.possible_causes = [soften(item) for item in output.possible_causes]
        output.pre_visit_checklist = [soften(item) for item in output.pre_visit_checklist]
        output.lifestyle_advice = [soften(item) for item in output.lifestyle_advice]
        return output
