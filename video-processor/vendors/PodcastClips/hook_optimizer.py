"""
Smart hook optimization for better engagement.

Analyzes content around detected moments to find the optimal starting point.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class HookOptimizer:
    """
    Optimize clip starting points for maximum engagement.

    Analyzes a window around the AI-detected moment to find:
    - Best sentence boundary (clean start)
    - Strongest opening (questions, controversy, emotion)
    - Optimal pacing (not mid-sentence or mid-word)
    """

    def __init__(self, search_window: float = 5.0):
        """
        Initialize hook optimizer.

        Args:
            search_window: Seconds to search before/after original timestamp
        """
        self.search_window = search_window

        # Sentence ending patterns
        self.sentence_enders = ['.', '!', '?']

        # Strong hook starters (regex patterns)
        self.hook_patterns = [
            r'^\s*(why|how|what|when|where|who)\b',  # Questions
            r'^\s*(never|always|you need|you should|you must)\b',  # Imperatives
            r'^\s*(secret|truth|revealed|exposed|shocking)\b',  # Revelations
            r'^\s*(here\'s|let me|i\'m going to)\b',  # Direct address
            r'^\s*(imagine|think about|what if)\b',  # Hypotheticals
        ]

    def optimize_clip_timing(
        self,
        original_start: float,
        original_end: float,
        word_timings: List[Dict[str, Any]],
        transcript_text: str
    ) -> Tuple[float, float, Dict[str, Any]]:
        """
        Optimize clip start and end times for better hooks.

        Args:
            original_start: Original start time from AI detection
            original_end: Original end time from AI detection
            word_timings: Full word timing data
            transcript_text: Full transcript text

        Returns:
            Tuple of (optimized_start, optimized_end, metadata)
        """
        logger.debug(f"Optimizing hook for clip {original_start:.1f}s-{original_end:.1f}s")

        # Find optimal start time
        optimized_start, start_meta = self._optimize_start_time(
            original_start,
            word_timings,
            transcript_text
        )

        # Adjust end time if needed (maintain similar duration)
        original_duration = original_end - original_start
        optimized_end = optimized_start + original_duration

        # Ensure end time lands on sentence boundary
        optimized_end = self._adjust_end_to_sentence(
            optimized_end,
            word_timings
        )

        metadata = {
            'original_start': original_start,
            'original_end': original_end,
            'optimized_start': optimized_start,
            'optimized_end': optimized_end,
            'adjustment_seconds': optimized_start - original_start,
            'start_optimization': start_meta
        }

        logger.info(f"Hook optimized: {original_start:.1f}s → {optimized_start:.1f}s (Δ{optimized_start-original_start:+.1f}s)")

        return optimized_start, optimized_end, metadata

    def _optimize_start_time(
        self,
        original_start: float,
        word_timings: List[Dict[str, Any]],
        transcript_text: str
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Find optimal start time within search window.

        Scores potential start points based on:
        1. Sentence boundaries (clean start)
        2. Hook strength (questions, strong openers)
        3. Proximity to original (prefer close matches)
        """
        # Define search window
        window_start = max(0, original_start - self.search_window)
        window_end = original_start + self.search_window

        # Get words in window
        window_words = [
            w for w in word_timings
            if window_start <= w.get('start_time', 0) <= window_end
        ]

        if not window_words:
            return original_start, {'reason': 'no_words_in_window'}

        # Find all sentence boundaries in window
        candidates = []

        for i, word in enumerate(window_words):
            # Check if this word starts a new sentence
            if i == 0 or self._is_sentence_start(window_words, i):
                # Build text from this point for analysis
                following_text = ' '.join([w['word'] for w in window_words[i:min(i+20, len(window_words))]])

                # Score this candidate
                score = self._score_start_candidate(
                    word['start_time'],
                    following_text,
                    original_start
                )

                candidates.append({
                    'time': word['start_time'],
                    'text_preview': following_text[:50],
                    'score': score,
                    'word_index': i
                })

        if not candidates:
            return original_start, {'reason': 'no_candidates'}

        # Select best candidate
        best = max(candidates, key=lambda c: c['score'])

        metadata = {
            'reason': 'optimized',
            'score': best['score'],
            'text_preview': best['text_preview'],
            'candidates_evaluated': len(candidates)
        }

        return best['time'], metadata

    def _is_sentence_start(self, words: List[Dict[str, Any]], index: int) -> bool:
        """
        Check if word at index starts a new sentence.

        Args:
            words: List of word dicts
            index: Current word index

        Returns:
            True if this word likely starts a sentence
        """
        if index == 0:
            return True

        prev_word = words[index - 1]['word'].strip()

        # Previous word ends with sentence ender
        if any(prev_word.endswith(ender) for ender in self.sentence_enders):
            return True

        # Current word is capitalized (rough heuristic)
        current_word = words[index]['word'].strip()
        if current_word and current_word[0].isupper():
            # Check if previous word was lowercase (not a proper noun)
            if prev_word and prev_word[0].islower():
                return True

        return False

    def _score_start_candidate(
        self,
        candidate_time: float,
        following_text: str,
        original_time: float
    ) -> float:
        """
        Score a candidate start time.

        Higher scores are better.

        Args:
            candidate_time: Candidate start timestamp
            following_text: Text following this start point
            original_time: Original AI-detected start time

        Returns:
            Score (0-100)
        """
        score = 50.0  # Base score

        text_lower = following_text.lower()

        # 1. Hook pattern bonus (+30 points max)
        for pattern in self.hook_patterns:
            if re.match(pattern, text_lower):
                score += 30.0
                break  # Only count one pattern

        # 2. Question bonus (+20 points)
        if '?' in following_text[:50]:  # Question in first ~10 words
            score += 20.0

        # 3. Proximity to original time (prefer close matches)
        # Closer to original = higher score
        time_diff = abs(candidate_time - original_time)
        if time_diff <= 1.0:
            proximity_bonus = 20.0
        elif time_diff <= 2.0:
            proximity_bonus = 15.0
        elif time_diff <= 3.0:
            proximity_bonus = 10.0
        else:
            proximity_bonus = 5.0

        score += proximity_bonus

        # 4. Emotional/engaging words bonus (+10 points)
        engaging_words = ['never', 'always', 'secret', 'truth', 'shocking', 'amazing', 'incredible']
        if any(word in text_lower for word in engaging_words):
            score += 10.0

        # 5. Penalize if starting mid-sentence (detected by lowercase first letter)
        if following_text and following_text[0].islower():
            score -= 15.0

        return max(0, min(score, 100))  # Clamp to 0-100

    def _adjust_end_to_sentence(
        self,
        target_end: float,
        word_timings: List[Dict[str, Any]]
    ) -> float:
        """
        Adjust end time to land on a sentence boundary.

        Args:
            target_end: Target end time
            word_timings: Word timing data

        Returns:
            Adjusted end time
        """
        # Find words around target end
        search_range = 3.0  # Search within 3 seconds
        nearby_words = [
            w for w in word_timings
            if target_end - search_range <= w.get('end_time', 0) <= target_end + search_range
        ]

        if not nearby_words:
            return target_end

        # Find nearest sentence ender
        best_end = target_end
        min_distance = float('inf')

        for word in nearby_words:
            word_text = word['word'].strip()
            word_end = word.get('end_time', target_end)

            # Check if word ends with sentence ender
            if any(word_text.endswith(ender) for ender in self.sentence_enders):
                distance = abs(word_end - target_end)
                if distance < min_distance:
                    min_distance = distance
                    best_end = word_end

        return best_end

    def batch_optimize_clips(
        self,
        clips: List[Dict[str, Any]],
        word_timings: List[Dict[str, Any]],
        transcript_text: str
    ) -> List[Dict[str, Any]]:
        """
        Optimize timing for multiple clips.

        Args:
            clips: List of clip dicts with 'start_time' and 'end_time'
            word_timings: Word timing data
            transcript_text: Full transcript

        Returns:
            Updated clips with optimized timing
        """
        logger.info(f"Optimizing hooks for {len(clips)} clips")

        optimized_clips = []

        for clip in clips:
            opt_start, opt_end, metadata = self.optimize_clip_timing(
                clip['start_time'],
                clip['end_time'],
                word_timings,
                transcript_text
            )

            # Update clip with optimized timing
            updated_clip = clip.copy()
            updated_clip['optimized_start'] = opt_start
            updated_clip['optimized_end'] = opt_end
            updated_clip['optimization_metadata'] = metadata

            optimized_clips.append(updated_clip)

        logger.info(f"Hook optimization complete for {len(optimized_clips)} clips")

        return optimized_clips
