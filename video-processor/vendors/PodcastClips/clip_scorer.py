"""
Clip quality scoring and ranking system.

Scores clips based on viral potential using multiple engagement factors.
"""

import logging
import re
from typing import List, Dict, Any
import math

logger = logging.getLogger(__name__)


class ClipScorer:
    """
    Score and rank podcast clips by viral potential.

    Analyzes:
    - Hook strength (first 3 seconds)
    - Content engagement factors
    - Duration optimization
    - Emotional resonance
    - Quotability
    """

    def __init__(self):
        """Initialize clip scorer."""
        # Viral keywords that indicate high engagement
        self.viral_keywords = {
            'high': ['secret', 'shocking', 'revealed', 'truth', 'exposed', 'mistake', 'wrong', 'fail', 'never', 'always'],
            'medium': ['important', 'better', 'best', 'worst', 'how', 'why', 'when', 'should', 'must'],
            'low': ['interesting', 'nice', 'good', 'think', 'maybe', 'perhaps']
        }

        # Emotion indicators
        self.emotion_keywords = {
            'excitement': ['amazing', 'incredible', 'unbelievable', 'wow', 'insane', 'crazy'],
            'controversy': ['wrong', 'disagree', 'hate', 'love', 'worst', 'best'],
            'surprise': ['shocked', 'unexpected', 'suddenly', 'realized', 'discovered'],
            'urgency': ['now', 'immediately', 'must', 'need', 'urgent', 'important']
        }

        # Question patterns (highly engaging)
        self.question_patterns = [
            r'\?',  # Direct questions
            r'\bwhy\b',
            r'\bhow\b',
            r'\bwhat if\b',
            r'\bcan you\b',
            r'\bshould\b'
        ]

    def score_clip(
        self,
        transcript_text: str,
        word_timings: List[Dict[str, Any]],
        start_time: float,
        end_time: float,
        title: str,
        reason: str,
        face_coverage: float = 0.0
    ) -> Dict[str, Any]:
        """
        Score a clip's viral potential.

        Args:
            transcript_text: Full transcript text for the clip
            word_timings: Word-level timing data
            start_time: Clip start time
            end_time: Clip end time
            title: Clip title
            reason: AI's reason for selecting this moment
            face_coverage: Percentage of frames with detected faces

        Returns:
            Dict with overall score and breakdown
        """
        scores = {}

        # 1. Hook Strength (first 3 seconds) - 25 points
        scores['hook'] = self._score_hook_strength(
            transcript_text, word_timings, start_time
        )

        # 2. Duration Score - 15 points
        scores['duration'] = self._score_duration(start_time, end_time)

        # 3. Content Engagement - 25 points
        scores['engagement'] = self._score_content_engagement(
            transcript_text, title, reason
        )

        # 4. Emotional Resonance - 15 points
        scores['emotion'] = self._score_emotional_content(transcript_text)

        # 5. Quotability - 10 points
        scores['quotability'] = self._score_quotability(transcript_text)

        # 6. Visual Quality - 10 points
        scores['visual'] = self._score_visual_quality(face_coverage)

        # Calculate total score (out of 100)
        total_score = sum(scores.values())

        return {
            'total_score': round(total_score, 2),
            'scores': scores,
            'grade': self._get_grade(total_score)
        }

    def _score_hook_strength(
        self,
        transcript: str,
        word_timings: List[Dict[str, Any]],
        start_time: float
    ) -> float:
        """
        Score hook strength (first 3 seconds).

        Strong hooks have:
        - Questions
        - Controversial statements
        - Strong emotion
        - Surprising statements

        Max: 25 points
        """
        score = 0.0

        # Extract first 3 seconds of text
        hook_end = start_time + 3.0
        hook_words = [
            w['word'] for w in word_timings
            if start_time <= w.get('start_time', 0) <= hook_end
        ]
        hook_text = ' '.join(hook_words).lower()

        if not hook_text:
            return 0.0

        # Questions in hook (+10 points)
        if any(re.search(pattern, hook_text) for pattern in self.question_patterns):
            score += 10.0

        # Viral keywords in hook
        for keyword in self.viral_keywords['high']:
            if keyword in hook_text:
                score += 3.0  # Up to +9 for 3 keywords
                if score >= 19:  # Cap at 19 from keywords
                    break

        # Emotional words in hook
        emotion_count = sum(
            1 for emotion_list in self.emotion_keywords.values()
            for keyword in emotion_list
            if keyword in hook_text
        )
        score += min(emotion_count * 2, 6)  # Up to +6 points

        return min(score, 25.0)

    def _score_duration(self, start_time: float, end_time: float) -> float:
        """
        Score clip duration (ideal: 30-60s).

        Max: 15 points
        """
        duration = end_time - start_time

        # Optimal duration: 30-60 seconds
        if 30 <= duration <= 60:
            return 15.0
        elif 20 <= duration < 30:
            # Good, but slightly short
            return 12.0
        elif 60 < duration <= 70:
            # Good, but slightly long
            return 12.0
        elif 15 <= duration < 20:
            # Too short, but acceptable
            return 8.0
        elif 70 < duration <= 90:
            # Too long, but acceptable
            return 8.0
        else:
            # Too short (<15s) or too long (>90s)
            return 3.0

    def _score_content_engagement(
        self,
        transcript: str,
        title: str,
        reason: str
    ) -> float:
        """
        Score content engagement based on keywords and patterns.

        Max: 25 points
        """
        score = 0.0
        text_lower = (transcript + ' ' + title + ' ' + reason).lower()

        # High-value viral keywords (+3 each, max 15)
        high_count = sum(1 for kw in self.viral_keywords['high'] if kw in text_lower)
        score += min(high_count * 3, 15)

        # Medium-value keywords (+1 each, max 5)
        medium_count = sum(1 for kw in self.viral_keywords['medium'] if kw in text_lower)
        score += min(medium_count * 1, 5)

        # Question marks (indicates engaging discussion) (+2 each, max 5)
        question_count = text_lower.count('?')
        score += min(question_count * 2, 5)

        return min(score, 25.0)

    def _score_emotional_content(self, transcript: str) -> float:
        """
        Score emotional resonance.

        Max: 15 points
        """
        score = 0.0
        text_lower = transcript.lower()

        # Count emotion indicators by category
        emotion_scores = {}
        for emotion_type, keywords in self.emotion_keywords.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            emotion_scores[emotion_type] = count

        # Multiple emotion types = more engaging (+5 per type, max 10)
        emotion_diversity = len([c for c in emotion_scores.values() if c > 0])
        score += min(emotion_diversity * 5, 10)

        # Raw emotion keyword count (+1 per keyword, max 5)
        total_emotion_words = sum(emotion_scores.values())
        score += min(total_emotion_words, 5)

        return min(score, 15.0)

    def _score_quotability(self, transcript: str) -> float:
        """
        Score how quotable/shareable the content is.

        Max: 10 points
        """
        score = 0.0

        # Short, punchy sentences are more quotable
        sentences = re.split(r'[.!?]', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        # Count short, impactful sentences (5-15 words)
        punchy_count = sum(1 for s in sentences if 5 <= len(s.split()) <= 15)
        score += min(punchy_count * 2, 6)

        # Exclamation marks indicate emphasis (+2 each, max 4)
        exclamation_count = transcript.count('!')
        score += min(exclamation_count * 2, 4)

        return min(score, 10.0)

    def _score_visual_quality(self, face_coverage: float) -> float:
        """
        Score visual quality based on face detection coverage.

        Max: 10 points
        """
        # Face coverage 0-100%
        # 80%+ coverage = full 10 points
        # Lower coverage = proportionally lower score

        if face_coverage >= 80:
            return 10.0
        elif face_coverage >= 50:
            return 8.0
        elif face_coverage >= 30:
            return 6.0
        elif face_coverage >= 10:
            return 4.0
        else:
            return 2.0  # Minimum score for any clip

    def _get_grade(self, score: float) -> str:
        """
        Convert numeric score to letter grade.

        Args:
            score: Score 0-100

        Returns:
            Letter grade (S, A, B, C, D, F)
        """
        if score >= 90:
            return 'S'  # Exceptional viral potential
        elif score >= 80:
            return 'A'  # Excellent viral potential
        elif score >= 70:
            return 'B'  # Good viral potential
        elif score >= 60:
            return 'C'  # Moderate viral potential
        elif score >= 50:
            return 'D'  # Low viral potential
        else:
            return 'F'  # Poor viral potential

    def rank_clips(
        self,
        clips_with_scores: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank clips by viral score (descending).

        Args:
            clips_with_scores: List of dicts with 'viral_score' and 'title'

        Returns:
            Sorted list (best first)
        """
        return sorted(
            clips_with_scores,
            key=lambda x: x.get('viral_score', 0),
            reverse=True
        )

    def filter_top_clips(
        self,
        clips_with_scores: List[Dict[str, Any]],
        target_count: int,
        min_score: float = 60.0
    ) -> List[Dict[str, Any]]:
        """
        Filter to top N clips meeting minimum quality threshold.

        Args:
            clips_with_scores: List of clips with scores
            target_count: Target number of clips
            min_score: Minimum score threshold (default: 60/100)

        Returns:
            Filtered and ranked list
        """
        # Filter by minimum score
        qualified_clips = [
            clip for clip in clips_with_scores
            if clip.get('viral_score', 0) >= min_score
        ]

        # Rank by score
        ranked = self.rank_clips(qualified_clips)

        # Return top N
        return ranked[:target_count]
