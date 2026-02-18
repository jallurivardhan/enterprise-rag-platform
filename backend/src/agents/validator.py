"""Validator agent for checking answer quality and groundedness."""

import re
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.retriever import RetrievedChunk
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class ValidationResult(BaseModel):
    """Result of answer validation."""

    is_valid: bool = Field(..., description="Whether the answer passes all critical checks")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score (0-1)")
    issues: list[str] = Field(default_factory=list, description="List of problems found")
    suggestions: Optional[str] = Field(None, description="Suggestions for improvement")
    is_grounded: bool = Field(..., description="Whether answer is supported by sources")
    check_results: dict[str, bool] = Field(
        default_factory=dict, description="Individual check results"
    )


class ValidatorAgent:
    """
    Agent responsible for validating answer quality and groundedness.
    
    Checks if answers are relevant, grounded in sources, and free of hallucinations.
    """

    def __init__(self, llm: Optional[ChatOpenAI] = None) -> None:
        """
        Initialize the validator agent.

        Args:
            llm: Optional ChatOpenAI instance for LLM-based validation. If None, uses rule-based validation.
        """
        self.llm = llm
        if self.llm is None and settings.OPENAI_API_KEY:
            try:
                self.llm = ChatOpenAI(
                    model="gpt-4-turbo-preview",
                    temperature=0.3,
                    api_key=settings.OPENAI_API_KEY,
                )
                logger.info("Validator agent initialized with LLM")
            except Exception as e:
                logger.warning("Failed to initialize LLM for validator, using rule-based", error=str(e))
                self.llm = None

        if self.llm is None:
            logger.info("Validator agent initialized with rule-based validation")

    def _check_length(self, answer: str) -> tuple[bool, float]:
        """
        Check if answer length is appropriate.

        Args:
            answer: Answer text to check

        Returns:
            tuple: (is_valid, score) where score is 0-1
        """
        length = len(answer.strip())
        min_length = 20
        max_length = 3000

        if length < min_length:
            return False, 0.3
        elif length > max_length:
            return False, 0.5
        elif length < 50:
            return True, 0.7  # Short but acceptable
        elif length > 2000:
            return True, 0.8  # Long but acceptable
        else:
            return True, 1.0  # Ideal length

    def _check_relevance(self, query: str, answer: str) -> tuple[bool, float]:
        """
        Check if answer is relevant to the query.

        Args:
            query: Original query
            answer: Answer text to check

        Returns:
            tuple: (is_valid, score) where score is 0-1
        """
        query_lower = query.lower()
        answer_lower = answer.lower()

        # Extract key terms from query (remove stop words)
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "can",
            "what",
            "which",
            "who",
            "whom",
            "whose",
            "where",
            "when",
            "why",
            "how",
        }

        query_words = set(
            word for word in query_lower.split() if word not in stop_words and len(word) > 2
        )

        if not query_words:
            # Query is all stop words, can't check relevance
            return True, 0.5

        # Check if answer contains query keywords
        answer_words = set(answer_lower.split())
        matching_words = query_words & answer_words

        # Calculate relevance score
        relevance_score = len(matching_words) / len(query_words) if query_words else 0.0

        # Also check for synonyms/related terms (simple heuristic)
        # Numbers and dates should match if present in query
        query_numbers = re.findall(r"\d+", query)
        answer_numbers = re.findall(r"\d+", answer)
        if query_numbers:
            number_match = any(q_num in answer_numbers for q_num in query_numbers)
            if number_match:
                relevance_score = min(1.0, relevance_score + 0.2)

        is_valid = relevance_score >= 0.3
        return is_valid, min(1.0, relevance_score)

    def _extract_claims(self, text: str) -> list[str]:
        """
        Extract key claims/phrases from text.

        Args:
            text: Text to extract claims from

        Returns:
            list[str]: List of key claims/phrases
        """
        # Simple extraction: sentences with numbers, dates, or specific facts
        sentences = re.split(r"[.!?]+", text)
        claims = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Look for sentences with:
            # - Numbers (facts, statistics)
            # - Dates
            # - Specific entities (capitalized words)
            # - Comparative words (more, less, increased, decreased)
            has_number = bool(re.search(r"\d+", sentence))
            has_date = bool(
                re.search(
                    r"\b(19|20)\d{2}\b|\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
                    sentence,
                    re.IGNORECASE,
                )
            )
            has_comparative = bool(
                re.search(
                    r"\b(more|less|increased|decreased|up|down|higher|lower|better|worse)\b",
                    sentence,
                    re.IGNORECASE,
                )
            )
            has_entity = bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", sentence))

            if has_number or has_date or (has_comparative and has_entity):
                # Extract key phrase (first 50 chars or whole sentence if shorter)
                claim = sentence[:50].strip() if len(sentence) > 50 else sentence.strip()
                if len(claim) > 10:  # Only meaningful claims
                    claims.append(claim.lower())

        # If no specific claims found, use first few sentences as claims
        if not claims:
            sentences = [s.strip() for s in sentences if s.strip()]
            claims = [s[:50].lower() for s in sentences[:3] if len(s) > 10]

        return claims

    def _fuzzy_match(self, claim: str, source_text: str, threshold: float = 0.6) -> bool:
        """
        Check if claim appears in source text using fuzzy matching.

        Args:
            claim: Claim to match
            source_text: Source text to search in
            threshold: Similarity threshold (0-1)

        Returns:
            bool: True if claim is found in source
        """
        claim_lower = claim.lower()
        source_lower = source_text.lower()

        # Exact match
        if claim_lower in source_lower:
            return True

        # Word overlap matching
        claim_words = set(word for word in claim_lower.split() if len(word) > 2)
        source_words = set(word for word in source_lower.split() if len(word) > 2)

        if not claim_words:
            return False

        intersection = len(claim_words & source_words)
        union = len(claim_words | source_words)
        similarity = intersection / union if union > 0 else 0.0

        return similarity >= threshold

    def _check_grounding(self, answer: str, sources: list[RetrievedChunk]) -> tuple[bool, float]:
        """
        Check if answer is grounded in sources.

        Args:
            answer: Answer text to check
            sources: List of source chunks

        Returns:
            tuple: (is_grounded, grounding_score) where score is 0-1
        """
        if not sources:
            return False, 0.0

        # Extract claims from answer
        claims = self._extract_claims(answer)

        if not claims:
            # No specific claims found, consider it grounded if answer is general
            return True, 0.5

        # Check each claim against sources
        grounded_claims = 0
        source_texts = " ".join([chunk.content for chunk in sources])

        for claim in claims:
            if self._fuzzy_match(claim, source_texts, threshold=0.5):
                grounded_claims += 1

        grounding_score = grounded_claims / len(claims) if claims else 0.0
        is_grounded = grounding_score >= 0.7

        logger.debug(
            "Grounding check",
            total_claims=len(claims),
            grounded_claims=grounded_claims,
            grounding_score=round(grounding_score, 2),
        )

        return is_grounded, grounding_score

    def _check_source_citation(self, answer: str) -> tuple[bool, float]:
        """
        Check if answer references sources (if citation is expected).

        Args:
            answer: Answer text to check

        Returns:
            tuple: (is_valid, score) where score is 0-1
        """
        # Look for citation patterns
        citation_patterns = [
            r"\[.*?\]",  # [1], [source], etc.
            r"\(.*?\)",  # (source), (page 1), etc.
            r"according to",
            r"as stated in",
            r"per the",
            r"source:",
            r"reference:",
        ]

        has_citation = any(re.search(pattern, answer, re.IGNORECASE) for pattern in citation_patterns)

        # Citations are optional for now, so this is informational
        if has_citation:
            return True, 1.0
        else:
            return True, 0.5  # Not required, but nice to have

    def _check_hallucination(self, answer: str, sources: list[RetrievedChunk]) -> tuple[bool, float]:
        """
        Basic check for hallucinations (facts not in sources).

        Args:
            answer: Answer text to check
            sources: List of source chunks

        Returns:
            tuple: (is_valid, score) where score is 0-1
        """
        if not sources:
            return True, 0.5  # Can't check without sources

        # Extract specific facts (numbers, dates, names)
        answer_numbers = set(re.findall(r"\d+", answer))
        answer_dates = set(re.findall(r"\b(19|20)\d{2}\b", answer))

        source_texts = " ".join([chunk.content for chunk in sources])
        source_numbers = set(re.findall(r"\d+", source_texts))
        source_dates = set(re.findall(r"\b(19|20)\d{2}\b", source_texts))

        # Check if numbers in answer appear in sources (allowing some flexibility)
        if answer_numbers:
            # Allow some numbers to be calculations or derived
            matching_numbers = answer_numbers & source_numbers
            number_match_ratio = len(matching_numbers) / len(answer_numbers) if answer_numbers else 1.0

            # If less than 50% of numbers match, might be hallucination
            if number_match_ratio < 0.5 and len(answer_numbers) > 2:
                return False, 0.3
        else:
            number_match_ratio = 1.0

        # Check dates
        if answer_dates:
            matching_dates = answer_dates & source_dates
            date_match_ratio = len(matching_dates) / len(answer_dates) if answer_dates else 1.0

            if date_match_ratio < 0.5:
                return False, 0.4
        else:
            date_match_ratio = 1.0

        # Overall score
        score = (number_match_ratio + date_match_ratio) / 2
        is_valid = score >= 0.5

        return is_valid, score

    async def validate(
        self, query: str, answer: str, sources: list[RetrievedChunk]
    ) -> ValidationResult:
        """
        Validate answer quality and groundedness.

        Args:
            query: Original query
            answer: Generated answer to validate
            sources: List of source chunks used to generate answer

        Returns:
            ValidationResult: Validation result with scores and issues
        """
        logger.info("Validating answer", query=query[:50], answer_length=len(answer))

        check_results = {}
        check_scores = {}
        issues = []

        # Run all checks
        length_valid, length_score = self._check_length(answer)
        check_results["length"] = length_valid
        check_scores["length"] = length_score
        if not length_valid:
            if len(answer.strip()) < 20:
                issues.append("Answer is too short (less than 20 characters)")
            else:
                issues.append("Answer is too long (more than 3000 characters)")

        relevance_valid, relevance_score = self._check_relevance(query, answer)
        check_results["relevance"] = relevance_valid
        check_scores["relevance"] = relevance_score
        if not relevance_valid:
            issues.append("Answer is not relevant to the query")

        is_grounded, grounding_score = self._check_grounding(answer, sources)
        check_results["grounding"] = is_grounded
        check_scores["grounding"] = grounding_score
        if not is_grounded:
            issues.append(f"Answer is not well-grounded in sources (grounding score: {grounding_score:.2f})")

        citation_valid, citation_score = self._check_source_citation(answer)
        check_results["citation"] = citation_valid
        check_scores["citation"] = citation_score
        # Citation is optional, so don't add to issues

        hallucination_valid, hallucination_score = self._check_hallucination(answer, sources)
        check_results["hallucination"] = hallucination_valid
        check_scores["hallucination"] = hallucination_score
        if not hallucination_valid:
            issues.append("Answer may contain information not found in sources (potential hallucination)")

        # Calculate overall confidence (weighted average)
        weights = {
            "length": 0.1,
            "relevance": 0.3,
            "grounding": 0.4,
            "citation": 0.05,
            "hallucination": 0.15,
        }

        confidence = sum(check_scores.get(check, 0.5) * weights.get(check, 0.0) for check in weights.keys())
        confidence = max(0.0, min(1.0, confidence))

        # Determine if answer is valid (critical checks must pass)
        critical_checks = ["length", "relevance", "grounding", "hallucination"]
        is_valid = all(check_results.get(check, False) for check in critical_checks)

        # Generate suggestions
        suggestions = self.suggest_improvement(
            ValidationResult(
                is_valid=is_valid,
                confidence=confidence,
                issues=issues,
                is_grounded=is_grounded,
                check_results=check_results,
            ),
            query,
        )

        result = ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions,
            is_grounded=is_grounded,
            check_results=check_results,
        )

        logger.info(
            "Validation completed",
            is_valid=is_valid,
            confidence=round(confidence, 2),
            is_grounded=is_grounded,
            issues_count=len(issues),
        )

        return result

    def suggest_improvement(self, validation_result: ValidationResult, query: str) -> str:
        """
        Suggest improvements based on validation results.

        Args:
            validation_result: Validation result to analyze
            query: Original query

        Returns:
            str: Suggestion text
        """
        suggestions = []

        if not validation_result.check_results.get("length", True):
            suggestions.append("Answer is too short. Try retrieving more context or expanding the response.")

        if not validation_result.check_results.get("relevance", True):
            suggestions.append("Answer doesn't seem relevant to the query. Consider refining the retrieval query.")

        if not validation_result.is_grounded:
            suggestions.append(
                "Answer is not well-grounded in sources. Try retrieving more relevant chunks or improving the retrieval strategy."
            )

        if not validation_result.check_results.get("hallucination", True):
            suggestions.append(
                "Answer may contain information not in sources. Verify facts against the retrieved documents."
            )

        if not validation_result.check_results.get("citation", True):
            suggestions.append("Consider adding source citations to improve traceability.")

        if not suggestions:
            return "Answer quality is good. No major improvements needed."

        return " ".join(suggestions)

    # Backward compatibility method for RAGPipeline
    async def validate_legacy(
        self, query: str, retrieved_docs: list[dict]
    ) -> dict[str, Any]:
        """
        Legacy validation method for backward compatibility.

        Args:
            query: Original query
            retrieved_docs: List of retrieved documents

        Returns:
            dict: Validation results in legacy format
        """
        # Convert to RetrievedChunk format
        chunks = []
        for doc in retrieved_docs:
            from src.agents.retriever import RetrievedChunk
            from src.services.document_processor import ChunkMetadata

            metadata = ChunkMetadata(**doc.get("metadata", {}))
            chunk = RetrievedChunk(
                content=doc.get("content", ""),
                metadata=metadata,
                score=doc.get("score", 0.0),
                rank=0,
            )
            chunks.append(chunk)

        # For legacy, we just return the docs (validation happens on answer)
        return {
            "validated_docs": retrieved_docs,
            "quality_score": 1.0,
            "relevance_scores": [],
        }
