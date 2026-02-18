"""Planner agent for deciding RAG approach."""

import re
from enum import Enum
from typing import List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class RouteType(str, Enum):
    """Routing options for query processing."""

    RAG_ONLY = "rag_only"  # Simple retrieval and generation
    RAG_WITH_RERANK = "rag_with_rerank"  # Retrieve, rerank results, then generate
    CLARIFY = "clarify"  # Query is ambiguous, ask for clarification
    REFUSE = "refuse"  # Query is out of scope or inappropriate


class Plan(BaseModel):
    """Plan for processing a query."""

    route: RouteType = Field(..., description="Routing strategy to use")
    reasoning: str = Field(..., description="Explanation of why this route was chosen")
    retrieval_query: str = Field(..., description="Optimized query for vector search")
    num_chunks: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score (0-1)")


class PlannerAgent:
    """
    Agent responsible for planning the RAG retrieval strategy.
    
    Analyzes queries and decides the best approach to answer them.
    Supports both LLM-based and rule-based planning.
    """

    # Common abbreviations and their expansions
    ABBREVIATIONS = {
        "q1": "first quarter",
        "q2": "second quarter",
        "q3": "third quarter",
        "q4": "fourth quarter",
        "ceo": "chief executive officer",
        "cfo": "chief financial officer",
        "cto": "chief technology officer",
        "api": "application programming interface",
        "ai": "artificial intelligence",
        "ml": "machine learning",
        "nlp": "natural language processing",
        "rag": "retrieval augmented generation",
        "hr": "human resources",
        "it": "information technology",
        "etc": "et cetera",
        "vs": "versus",
        "e.g.": "for example",
        "i.e.": "that is",
    }

    # Filler words to remove
    FILLER_WORDS = {
        "um",
        "uh",
        "like",
        "basically",
        "actually",
        "literally",
        "you know",
        "i mean",
        "sort of",
        "kind of",
        "pretty much",
    }

    # Harmful content patterns (simple keyword-based)
    HARMFUL_PATTERNS = [
        r"\b(hack|exploit|attack|breach|malware|virus)\b",
        r"\b(illegal|unlawful|criminal)\s+(activity|action|act)\b",
        r"\b(personal|private)\s+(information|data|details)\s+(of|about)\s+(someone|anyone)\b",
    ]

    def __init__(self, llm: Optional[ChatOpenAI] = None) -> None:
        """
        Initialize the planner agent.

        Args:
            llm: Optional ChatOpenAI instance for LLM-based planning. If None, uses rule-based planning.
        """
        self.llm = llm
        if self.llm is None and settings.OPENAI_API_KEY:
            try:
                self.llm = ChatOpenAI(
                    model="gpt-4-turbo-preview",
                    temperature=0.3,  # Lower temperature for more consistent planning
                    api_key=settings.OPENAI_API_KEY,
                )
                logger.info("Planner agent initialized with LLM")
            except Exception as e:
                logger.warning("Failed to initialize LLM for planner, using rule-based", error=str(e))
                self.llm = None

        if self.llm is None:
            logger.info("Planner agent initialized with rule-based planning")

    def _optimize_query(self, query: str) -> str:
        """
        Optimize query for retrieval by removing filler words, expanding abbreviations, etc.

        Args:
            query: Original query

        Returns:
            str: Optimized query
        """
        # Convert to lowercase for processing
        optimized = query.lower().strip()

        # Remove filler words
        words = optimized.split()
        words = [w for w in words if w not in self.FILLER_WORDS]
        optimized = " ".join(words)

        # Expand abbreviations
        for abbrev, expansion in self.ABBREVIATIONS.items():
            # Match whole word abbreviations
            pattern = r"\b" + re.escape(abbrev) + r"\b"
            optimized = re.sub(pattern, expansion, optimized, flags=re.IGNORECASE)

        # Remove excessive whitespace
        optimized = re.sub(r"\s+", " ", optimized).strip()

        # Remove trailing punctuation that might interfere
        optimized = re.sub(r"[.,;:!?]+$", "", optimized).strip()

        logger.debug("Query optimized", original=query, optimized=optimized)
        return optimized

    def _extract_key_concepts(self, query: str) -> list[str]:
        """
        Extract key concepts and entities from query.

        Args:
            query: Query text

        Returns:
            list[str]: List of key concepts
        """
        # Simple extraction: remove stop words and get meaningful terms
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

        words = re.findall(r"\b\w+\b", query.lower())
        concepts = [w for w in words if w not in stop_words and len(w) > 2]
        return concepts

    def _check_harmful_content(self, query: str) -> bool:
        """
        Check if query contains potentially harmful content.

        Args:
            query: Query text

        Returns:
            bool: True if harmful content detected
        """
        query_lower = query.lower()
        for pattern in self.HARMFUL_PATTERNS:
            if re.search(pattern, query_lower):
                logger.warning("Harmful content detected in query", pattern=pattern)
                return True
        return False

    def _rule_based_plan(self, query: str) -> Plan:
        """Simple rule-based planning - always try RAG first."""
        # Clean and optimize query
        optimized_query = self._optimize_query(query)
        
        # Always use RAG_ONLY - let the retriever do the work
        return Plan(
            route=RouteType.RAG_ONLY,
            reasoning="Using RAG to retrieve relevant documents",
            retrieval_query=optimized_query if optimized_query else query,
            num_chunks=5,
            confidence=0.8
        )

    async def _llm_based_plan(self, query: str, chat_history: Optional[list] = None) -> Plan:
        """
        Create a plan using LLM-based logic.

        Args:
            query: User query
            chat_history: Optional chat history for context

        Returns:
            Plan: Planning decision
        """
        # Check for harmful content first (rule-based check)
        if self._check_harmful_content(query):
            return Plan(
                route=RouteType.REFUSE,
                reasoning="Query contains potentially harmful or inappropriate content",
                retrieval_query="",
                num_chunks=0,
                confidence=0.9,
            )

        # Build prompt for LLM
        prompt = f"""You are a query planning agent for a RAG (Retrieval-Augmented Generation) system.

Your task is to analyze the user's query and decide:
1. The best routing strategy
2. An optimized query for vector search
3. How many document chunks to retrieve

Routing options:
- RAG_ONLY: Simple retrieval and generation (for straightforward questions)
- RAG_WITH_RERANK: Retrieve, rerank results, then generate (for complex or multi-part questions)
- CLARIFY: Query is ambiguous or unclear (ask user for clarification)
- REFUSE: Query is out of scope, inappropriate, or cannot be answered from documents

Query optimization guidelines:
- Remove filler words ("um", "like", "basically")
- Expand common abbreviations (Q3 -> third quarter, CEO -> chief executive officer)
- Extract key entities and concepts
- Keep the core meaning intact

User Query: "{query}"

Analyze this query and respond in the following JSON format:
{{
    "route": "rag_only" | "rag_with_rerank" | "clarify" | "refuse",
    "reasoning": "Brief explanation of why this route was chosen",
    "retrieval_query": "Optimized query for vector search",
    "num_chunks": <number between 3 and 10>,
    "confidence": <number between 0.0 and 1.0>
}}

Respond with ONLY valid JSON, no additional text."""

        try:
            response = await self.llm.ainvoke(prompt)
            response_text = response.content.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # Parse JSON response
            import json

            plan_data = json.loads(response_text)

            # Validate and create Plan
            route_str = plan_data.get("route", "rag_only")
            try:
                route = RouteType(route_str)
            except ValueError:
                # Invalid route value, default to RAG_ONLY
                logger.warning("Invalid route value from LLM, defaulting to RAG_ONLY", route=route_str)
                route = RouteType.RAG_ONLY
            reasoning = plan_data.get("reasoning", "LLM-based planning decision")
            retrieval_query = plan_data.get("retrieval_query", self._optimize_query(query))
            num_chunks = max(3, min(10, plan_data.get("num_chunks", 5)))
            confidence = max(0.0, min(1.0, plan_data.get("confidence", 0.8)))

            plan = Plan(
                route=route,
                reasoning=reasoning,
                retrieval_query=retrieval_query,
                num_chunks=num_chunks,
                confidence=confidence,
            )

            logger.info(
                "LLM-based plan created",
                query=query[:100],
                route=route.value,
                num_chunks=num_chunks,
                confidence=confidence,
            )

            return plan

        except Exception as e:
            logger.warning(
                "LLM-based planning failed, falling back to rule-based",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Fallback to rule-based planning
            return self._rule_based_plan(query)

    async def plan(self, query: str, chat_history: Optional[List] = None) -> Plan:
        """Create a plan for the query - always use RAG."""
        # Clean the query
        clean_query = query.strip()
        
        # Optimize query (remove filler words)
        optimized = self._optimize_query(clean_query) if hasattr(self, '_optimize_query') else clean_query
        
        # ALWAYS return RAG_ONLY - no exceptions
        return Plan(
            route=RouteType.RAG_ONLY,
            reasoning="Using RAG retrieval to find relevant documents",
            retrieval_query=optimized if optimized else clean_query,
            num_chunks=5,
            confidence=0.9
        )
