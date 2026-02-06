"""
Scoring service for evaluating user answers.

Uses lightweight text similarity methods that don't require heavy dependencies like torch.
"""

from typing import Optional, Tuple
import re
import math
from collections import Counter

import requests

from ..config import Config, ScoringConfig, LLMConfig, EmbeddingConfig
from ..utils import is_online


class ScoringService:
    """
    Service for scoring user answers against expected answers.
    Supports text similarity, LLM evaluation, or hybrid approach.
    """

    def __init__(self, config: Config):
        self.scoring_config = config.scoring
        self.llm_config = config.llm
        self.embedding_config = config.embedding

        self._openai_client = None
        self._anthropic_client = None
        self._mistral_session: Optional[requests.Session] = None
        self._debug_logger = None  # Optional external logger

    def set_debug_logger(self, logger):
        """Set an external debug logger function."""
        self._debug_logger = logger

    def _log(self, message: str, level: str = "scoring"):
        """Log a debug message."""
        # Log to file
        from ..utils.logger import log_scoring, log_error, log_warning
        if level == "error":
            log_error(f"[SCORING] {message}")
        elif level == "warning":
            log_warning(f"[SCORING] {message}")
        else:
            log_scoring(message)

        # Log to debug panel if available
        if self._debug_logger:
            self._debug_logger(message, level)
        print(f"[SCORING {level.upper()}] {message}")

    def score_answer(
        self,
        user_answer: str,
        expected_answer: str,
        front_content: str = "",
    ) -> Tuple[float, int]:
        """
        Score the user's answer.

        Args:
            user_answer: What the user said
            expected_answer: The expected answer (back of card)
            front_content: The front of the card (for LLM context)

        Returns:
            Tuple of (score 0.0-1.0, rating 1-4)
        """
        if not user_answer or not user_answer.strip():
            self._log("Empty answer, returning score 0", "warning")
            return 0.0, 1

        method = self.scoring_config.method
        self._log(f"Scoring method: {method}")

        if method == "embedding":
            self._log(
                f"Using embedding similarity (provider: {self.embedding_config.provider})")
            score = self._score_with_similarity(user_answer, expected_answer)
            self._log(f"Embedding similarity score: {score:.3f}")
        elif method == "llm":
            self._log(
                f"Using LLM scoring (provider: {self.llm_config.provider})")
            score = self._score_with_llm(
                user_answer, expected_answer, front_content)
            self._log(f"LLM score: {score:.3f}")
        elif method == "hybrid":
            self._log(
                f"Using hybrid scoring (weight: {self.scoring_config.embedding_weight})")
            sim_score = self._score_with_similarity(
                user_answer, expected_answer)
            self._log(f"Embedding similarity: {sim_score:.3f}")
            llm_score = self._score_with_llm(
                user_answer, expected_answer, front_content)
            self._log(f"LLM score: {llm_score:.3f}")

            # Weighted average
            weight = self.scoring_config.embedding_weight
            score = (sim_score * weight) + (llm_score * (1 - weight))
            self._log(f"Hybrid combined score: {score:.3f}")
        else:
            score = self._score_with_similarity(user_answer, expected_answer)

        rating = self._score_to_rating(score)
        self._log(f"Final: score={score:.3f} → rating={rating}", "success")
        return score, rating

    def _score_with_similarity(self, user_answer: str, expected_answer: str) -> float:
        """Score using text similarity methods."""
        try:
            # Try spaCy embeddings if configured
            if self.embedding_config.provider == "spacy":
                return self._spacy_similarity(user_answer, expected_answer)

            # Try OpenAI embeddings if available and online
            if self.embedding_config.provider == "openai" and is_online() and self.llm_config.openai_api_key:
                return self._openai_embedding_similarity(user_answer, expected_answer)

            # Fall back to local text similarity
            return self._combined_text_similarity(user_answer, expected_answer)
        except Exception as e:
            print(f"Similarity scoring error: {e}")
            return self._simple_text_similarity(user_answer, expected_answer)

    def _combined_text_similarity(self, text1: str, text2: str) -> float:
        """
        Combined text similarity using multiple lightweight methods.
        No heavy dependencies required.
        """
        # Normalize texts
        text1_clean = self._normalize_text(text1)
        text2_clean = self._normalize_text(text2)

        if not text1_clean or not text2_clean:
            return 0.0

        # Calculate multiple similarity scores
        jaccard = self._jaccard_similarity(text1_clean, text2_clean)
        cosine = self._tfidf_cosine_similarity(text1_clean, text2_clean)
        sequence = self._sequence_similarity(text1_clean, text2_clean)

        # Weighted combination (cosine TF-IDF is usually best for semantic similarity)
        score = (cosine * 0.5) + (jaccard * 0.25) + (sequence * 0.25)

        return min(1.0, max(0.0, score))

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower()
        # Remove punctuation except spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text

    def _tokenize(self, text: str) -> list:
        """Simple tokenization."""
        return text.lower().split()

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity (word overlap)."""
        words1 = set(self._tokenize(text1))
        words2 = set(self._tokenize(text2))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _tfidf_cosine_similarity(self, text1: str, text2: str) -> float:
        """
        TF-IDF based cosine similarity.
        Lightweight implementation without sklearn.
        """
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)

        if not words1 or not words2:
            return 0.0

        # Build vocabulary
        all_words = set(words1) | set(words2)

        # Calculate term frequencies
        tf1 = Counter(words1)
        tf2 = Counter(words2)

        # Calculate TF-IDF vectors (simplified: IDF is 1 for words in both, 0.5 for words in one)
        vec1 = []
        vec2 = []

        for word in all_words:
            # TF component
            freq1 = tf1.get(word, 0) / len(words1) if words1 else 0
            freq2 = tf2.get(word, 0) / len(words2) if words2 else 0

            # Simple IDF: boost words that appear in both texts
            idf = 1.0 if (word in tf1 and word in tf2) else 0.5

            vec1.append(freq1 * idf)
            vec2.append(freq2 * idf)

        # Cosine similarity
        return self._cosine_similarity_vectors(vec1, vec2)

    def _sequence_similarity(self, text1: str, text2: str) -> float:
        """
        Sequence-based similarity using longest common subsequence ratio.
        Good for catching similar phrasing.
        """
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)

        if not words1 or not words2:
            return 0.0

        # LCS length
        lcs_len = self._lcs_length(words1, words2)

        # Normalize by average length
        avg_len = (len(words1) + len(words2)) / 2
        return lcs_len / avg_len if avg_len > 0 else 0.0

    def _lcs_length(self, seq1: list, seq2: list) -> int:
        """Calculate length of longest common subsequence."""
        m, n = len(seq1), len(seq2)

        # Optimize for memory: only keep two rows
        prev = [0] * (n + 1)
        curr = [0] * (n + 1)

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    curr[j] = prev[j-1] + 1
                else:
                    curr[j] = max(prev[j], curr[j-1])
            prev, curr = curr, [0] * (n + 1)

        return prev[n]

    def _cosine_similarity_vectors(self, vec1: list, vec2: list) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2) or not vec1:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _spacy_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity using spaCy word vectors.

        Uses small spaCy models (~15MB) which include word vectors.
        Much lighter than torch-based solutions (~1.7GB).
        """
        try:
            import spacy
        except ImportError:
            print("spaCy not installed, falling back to text similarity")
            return self._combined_text_similarity(text1, text2)

        # Get or load the spaCy model
        nlp = self._get_spacy_model()
        if nlp is None:
            return self._combined_text_similarity(text1, text2)

        # Process texts
        doc1 = nlp(text1)
        doc2 = nlp(text2)

        # spaCy's similarity uses word vectors
        similarity = doc1.similarity(doc2)

        # Normalize to 0-1 range (spaCy can return negative values)
        return max(0.0, min(1.0, (similarity + 1) / 2))

    def _get_spacy_model(self):
        """Get or load the spaCy model based on config language."""
        if not hasattr(self, '_spacy_nlp') or self._spacy_nlp is None:
            try:
                import sys
                from pathlib import Path

                # Determine model based on config language
                from ..deps import SPACY_MODELS
                lang = "en"  # Could extend to use self.config language
                model_name = SPACY_MODELS.get(lang, "en_core_web_sm")

                # Add bundled model path to sys.path if not already there
                addon_dir = Path(__file__).parent.parent
                bundled_model_dir = addon_dir / "vendor" / "spacy_models" / model_name
                if bundled_model_dir.exists() and str(bundled_model_dir) not in sys.path:
                    sys.path.insert(0, str(bundled_model_dir))

                try:
                    # Try to import the model as a package
                    if model_name == "en_core_web_sm":
                        import en_core_web_sm
                        self._spacy_nlp = en_core_web_sm.load()
                    elif model_name == "de_core_news_sm":
                        import de_core_news_sm
                        self._spacy_nlp = de_core_news_sm.load()
                    else:
                        # Fall back to spacy.load for system-installed models
                        import spacy
                        self._spacy_nlp = spacy.load(model_name)
                except (ImportError, OSError) as e:
                    print(f"spaCy model '{model_name}' not found: {e}")
                    self._spacy_nlp = None
            except ImportError:
                self._spacy_nlp = None

        return self._spacy_nlp

    def _openai_embedding_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity using OpenAI embeddings."""
        client = self._get_openai_client()
        if client is None:
            return self._combined_text_similarity(text1, text2)

        response = client.embeddings.create(
            model=self.embedding_config.openai_model,
            input=[text1, text2]
        )

        emb1 = response.data[0].embedding
        emb2 = response.data[1].embedding

        similarity = self._cosine_similarity_vectors(emb1, emb2)
        # OpenAI embeddings are normalized, so similarity is already in [-1, 1]
        return (similarity + 1) / 2

    def _simple_text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity fallback using word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _has_api_key_for_provider(self, provider: str) -> bool:
        """Check if API key is configured for the given provider."""
        if provider == "openai":
            return bool(self.llm_config.openai_api_key)
        elif provider == "anthropic":
            return bool(self.llm_config.anthropic_api_key)
        elif provider == "mistral":
            return bool(self.llm_config.mistral_api_key)
        elif provider == "ollama":
            return True  # Ollama doesn't need an API key
        return False

    def _score_with_llm(
        self,
        user_answer: str,
        expected_answer: str,
        front_content: str
    ) -> float:
        """Score using LLM evaluation."""
        provider = self.llm_config.provider

        # Check if API key is configured for the provider
        if not self._has_api_key_for_provider(provider):
            self._log(
                f"LLM {provider}: No API key configured, falling back to similarity", "warning")
            # No API key - fall back to text similarity (works like online mode)
            return self._score_with_similarity(user_answer, expected_answer)

        if not is_online():
            # Try local Ollama
            if provider == "ollama":
                self._log(
                    f"Using local Ollama (model: {self.llm_config.ollama_model})", "ai")
                return self._score_with_ollama(user_answer, expected_answer, front_content)
            self._log("Offline, falling back to similarity", "warning")
            # Fall back to similarity
            return self._score_with_similarity(user_answer, expected_answer)

        try:
            if provider == "openai":
                self._log(
                    f"Calling OpenAI (model: {self.llm_config.openai_model})", "ai")
                return self._score_with_openai(user_answer, expected_answer, front_content)
            elif provider == "anthropic":
                self._log(
                    f"Calling Anthropic (model: {self.llm_config.anthropic_model})", "ai")
                return self._score_with_anthropic(user_answer, expected_answer, front_content)
            elif provider == "mistral":
                self._log(
                    f"Calling Mistral (model: {self.llm_config.mistral_model})", "ai")
                return self._score_with_mistral(user_answer, expected_answer, front_content)
            elif provider == "ollama":
                self._log(
                    f"Calling Ollama (model: {self.llm_config.ollama_model})", "ai")
                return self._score_with_ollama(user_answer, expected_answer, front_content)
            else:
                return self._score_with_similarity(user_answer, expected_answer)

        except Exception as e:
            self._log(f"LLM ERROR: {e}", "error")
            self._log("Falling back to text similarity scoring", "warning")
            fallback_score = self._score_with_similarity(
                user_answer, expected_answer)
            self._log(
                f"Fallback similarity score: {fallback_score:.3f}", "info")
            return fallback_score

    def _build_scoring_prompt(self, front_content: str, expected_answer: str, user_answer: str) -> str:
        template = self.llm_config.scoring_prompt
        return template.format(front=front_content, back=expected_answer, user_answer=user_answer)

    def _score_with_openai(
        self,
        user_answer: str,
        expected_answer: str,
        front_content: str
    ) -> float:
        """Score using OpenAI."""
        client = self._get_openai_client()
        if client is None:
            return self._score_with_similarity(user_answer, expected_answer)

        prompt = self._build_scoring_prompt(
            front_content, expected_answer, user_answer)

        response = client.chat.completions.create(
            model=self.llm_config.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=10
        )

        return self._parse_llm_score(response.choices[0].message.content)

    def _score_with_anthropic(
        self,
        user_answer: str,
        expected_answer: str,
        front_content: str
    ) -> float:
        """Score using Anthropic Claude."""
        client = self._get_anthropic_client()
        if client is None:
            return self._score_with_similarity(user_answer, expected_answer)

        prompt = self._build_scoring_prompt(
            front_content, expected_answer, user_answer)

        response = client.messages.create(
            model=self.llm_config.anthropic_model,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_llm_score(response.content[0].text)

    def _score_with_mistral(
        self,
        user_answer: str,
        expected_answer: str,
        front_content: str
    ) -> float:
        """Score using Mistral Small."""
        api_key = self.llm_config.mistral_api_key
        if not api_key:
            return self._score_with_similarity(user_answer, expected_answer)

        prompt = self._build_scoring_prompt(
            front_content, expected_answer, user_answer)

        session = self._get_mistral_session()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.llm_config.mistral_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 10,
        }

        response = session.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Mistral response missing choices")

        message = choices[0].get("message", {})
        content = message.get("content", "0.5")
        if isinstance(content, list):
            text_chunks = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("text"):
                        text_chunks.append(part["text"])
                    elif part.get("type") == "text" and part.get("content"):
                        text_chunks.append(part["content"])
            content = "\n".join(text_chunks) if text_chunks else "0.5"

        return self._parse_llm_score(content)

    def _score_with_ollama(
        self,
        user_answer: str,
        expected_answer: str,
        front_content: str
    ) -> float:
        """Score using local Ollama."""
        import httpx

        prompt = self._build_scoring_prompt(
            front_content, expected_answer, user_answer)

        try:
            response = httpx.post(
                f"{self.llm_config.ollama_base_url}/api/generate",
                json={
                    "model": self.llm_config.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=30.0
            )
            response.raise_for_status()

            result = response.json()
            return self._parse_llm_score(result.get("response", "0.5"))

        except Exception as e:
            print(f"Ollama error: {e}")
            return self._score_with_similarity(user_answer, expected_answer)

    def _parse_llm_score(self, response: str) -> float:
        """Parse LLM response to extract score."""
        # Try to find a float between 0 and 1
        matches = re.findall(r'0?\.\d+|1\.0|0|1', response.strip())

        if matches:
            try:
                score = float(matches[0])
                return max(0.0, min(1.0, score))
            except ValueError:
                pass

        return 0.5  # Default to middle score

    def _score_to_rating(self, score: float) -> int:
        """Convert score to Anki rating (1-4)."""
        if score >= self.scoring_config.threshold_4:
            return 4  # Easy
        elif score >= self.scoring_config.threshold_3:
            return 3  # Good
        elif score >= self.scoring_config.threshold_2:
            return 2  # Hard
        else:
            return 1  # Again

    def _get_openai_client(self):
        """Get OpenAI client."""
        if self._openai_client is None and self.llm_config.openai_api_key:
            from openai import OpenAI
            self._openai_client = OpenAI(
                api_key=self.llm_config.openai_api_key)
        return self._openai_client

    def _get_anthropic_client(self):
        """Get Anthropic client."""
        if self._anthropic_client is None and self.llm_config.anthropic_api_key:
            from anthropic import Anthropic
            self._anthropic_client = Anthropic(
                api_key=self.llm_config.anthropic_api_key)
        return self._anthropic_client

    def _get_mistral_session(self) -> requests.Session:
        if self._mistral_session is None:
            self._mistral_session = requests.Session()
        return self._mistral_session

    def get_rating_description(self, rating: int) -> str:
        """Get human-readable description of rating."""
        descriptions = {
            1: "Again - Let's review this one more time",
            2: "Hard - That was difficult, but you got some of it",
            3: "Good - Nice job!",
            4: "Easy - Perfect!",
        }
        return descriptions.get(rating, "Unknown rating")

    def cleanup(self):
        """Clean up resources."""
        self._openai_client = None
        self._anthropic_client = None
        if self._mistral_session is not None:
            self._mistral_session.close()
            self._mistral_session = None
