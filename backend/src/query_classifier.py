"""Query complexity classifier for choosing between Normal RAG and Agentic RAG."""

import json
import re
from typing import Literal
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from src.core.config import settings
from src.core.logging import get_logger


class QueryClassification(BaseModel):
    """Result of query complexity classification."""

    complexity: Literal["simple", "complex"] = Field(
        ..., description="Query complexity level"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence"
    )
    reasoning: str = Field(..., description="Why this classification was chosen")
    recommended_mode: Literal["normal", "agentic"] = Field(
        ..., description="Recommended RAG mode"
    )
    indicators: list[str] = Field(
        default_factory=list, description="Complexity indicators found"
    )


class QueryClassifier:
    """Classifies queries to determine optimal RAG mode."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.logger = get_logger(__name__)

        # Patterns that indicate complex queries (rule-based fast check)
        self.complex_patterns = [
            r"\b(compare|comparison|versus|vs\.?|differ|difference)\b",
            r"\b(analyze|analysis|evaluate|assessment)\b",
            r"\b(how does .+ relate to|relationship between)\b",
            r"\b(pros? and cons?|advantages? and disadvantages?)\b",
            r"\b(step[- ]by[- ]step|explain .+ in detail)\b",
            r"\b(multiple|several|all|each|every)\b.+\b(documents?|files?|sources?)\b",
            r"\b(summarize|overview|comprehensive)\b",
            r"\band\b.+\band\b",  # Multiple "and"s suggest multi-part query
            r"\?.*\?",  # Multiple question marks
        ]

        # Patterns that indicate simple queries
        self.simple_patterns = [
            r"^what is\b",
            r"^who is\b",
            r"^when (did|was|is)\b",
            r"^where (is|was|are)\b",
            r"^define\b",
            r"^list\b",
        ]

    def _rule_based_classify(self, query: str) -> tuple[str, float, list[str]]:
        """Fast rule-based classification."""
        query_lower = query.lower().strip()
        indicators = []

        # Check for simple patterns first
        for pattern in self.simple_patterns:
            if re.search(pattern, query_lower):
                return "simple", 0.8, ["matches simple query pattern"]

        # Check for complex patterns
        complex_score = 0
        for pattern in self.complex_patterns:
            if re.search(pattern, query_lower):
                complex_score += 1
                indicators.append(f"pattern: {pattern[:30]}...")

        # Check query length (longer queries tend to be complex)
        word_count = len(query.split())
        if word_count > 20:
            complex_score += 1
            indicators.append(f"long query ({word_count} words)")

        # Check for multiple clauses
        clause_markers = [",", ";", " and ", " or ", " but "]
        clause_count = sum(query_lower.count(marker) for marker in clause_markers)
        if clause_count >= 2:
            complex_score += 1
            indicators.append(f"multiple clauses ({clause_count})")

        if complex_score >= 2:
            confidence = min(0.9, 0.6 + (complex_score * 0.1))
            return "complex", confidence, indicators
        elif complex_score == 1:
            return "complex", 0.6, indicators
        else:
            return "simple", 0.75, ["no complexity indicators found"]

    async def classify(
        self, query: str, use_llm: bool = False
    ) -> QueryClassification:
        """
        Classify query complexity.

        Args:
            query: The user's query
            use_llm: Whether to use LLM for classification (slower but more accurate)

        Returns:
            QueryClassification with complexity level and recommended mode
        """
        # First, try rule-based classification
        complexity, confidence, indicators = self._rule_based_classify(query)

        # If confidence is low or use_llm is True, use LLM for better accuracy
        if use_llm or confidence < 0.7:
            try:
                llm_result = await self._llm_classify(query)
                if llm_result:
                    complexity = llm_result["complexity"]
                    confidence = llm_result["confidence"]
                    indicators = llm_result.get("indicators", indicators)
            except Exception as e:
                self.logger.warning(f"LLM classification failed, using rule-based: {e}")

        recommended_mode = "agentic" if complexity == "complex" else "normal"
        reasoning = self._generate_reasoning(complexity, indicators)

        return QueryClassification(
            complexity=complexity,
            confidence=confidence,
            reasoning=reasoning,
            recommended_mode=recommended_mode,
            indicators=indicators,
        )

    async def _llm_classify(self, query: str) -> dict:
        """Use LLM for more accurate classification."""
        prompt = f"""Classify this query's complexity for a RAG (Retrieval-Augmented Generation) system.

Query: "{query}"

Classification criteria:
- SIMPLE: Single topic, straightforward lookup, factual question, definition request
- COMPLEX: Multiple topics, comparison, analysis, multi-part question, requires synthesis from multiple sources

Respond with ONLY a JSON object:
{{"complexity": "simple" or "complex", "confidence": 0.0-1.0, "indicators": ["reason1", "reason2"]}}"""

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )

        content = response.choices[0].message.content.strip()
        return json.loads(content)

    def _generate_reasoning(self, complexity: str, indicators: list[str]) -> str:
        """Generate human-readable reasoning."""
        if complexity == "complex":
            return f"Query classified as complex due to: {', '.join(indicators[:3])}"
        else:
            return "Query is straightforward and can be answered with single retrieval"


# Singleton instance
query_classifier = QueryClassifier()
