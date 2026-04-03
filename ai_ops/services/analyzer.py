import logging

from ..models import Incident
from .sre_agent import run_sre_agent_analysis

logger = logging.getLogger(__name__)


class FaultAnalyzer:
    """Runs the DeepSeek / OpenAI-compatible ReAct SRE agent (function calling)."""

    def __init__(self, incident: Incident):
        self.incident = incident

    def analyze(self):
        logger.info("SRE agent analysis start incident=%s", self.incident.id)
        run_sre_agent_analysis(self.incident)

    def finalize_with_user_evidence(self, evidence_updates: dict):
        raise RuntimeError(
            "人工粘贴证据流程已移除；告警由 SRE Agent 自动调用工具完成分析。"
        )
