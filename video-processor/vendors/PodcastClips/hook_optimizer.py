"""
Smart hook optimization for better engagement.

Analyzes content around detected moments to find the optimal starting point.
"""

from loguru import logger as loguru_logger
import re
from typing import List, Dict, Any, Optional, Tuple

logger = loguru_logger.bind(name="PodcastClips.hook_optimizer")


class HookOptimizer:
    """
    Optimize clip starting points for maximum engagement.

    Analyzes a window around the AI-detected moment to find:
    - Best sentence boundary (clean start)
    - Strongest opening (questions, controversy, emotion)
    - Optimal pacing (not mid-sentence or mid-word)
    """

    def __init__(self, search_window: float = 10.0, pause_threshold: float = 0.3, padding: float = 0.2):
        """
        Initialize hook optimizer.

        Args:
            search_window: Seconds to search before/after original timestamp
            pause_threshold: Minimum pause duration (in seconds) to consider as sentence boundary
            padding: Seconds to add before start and after end to avoid clipping words
        """
        self.search_window = search_window
        self.pause_threshold = pause_threshold  # Detect pauses >= 0.3 seconds
        self.padding = padding  # Add 0.2s padding to avoid clipping

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

        # Apply padding to avoid clipping words at boundaries
        # Subtract padding from start (but don't go below 0)
        padded_start = max(0, optimized_start - self.padding)
        # Add padding to end
        padded_end = optimized_end + self.padding

        metadata = {
            'original_start': original_start,
            'original_end': original_end,
            'optimized_start': padded_start,
            'optimized_end': padded_end,
            'adjustment_seconds': padded_start - original_start,
            'start_optimization': start_meta,
            'padding_applied': self.padding
        }

        logger.info(f"Hook optimized: {original_start:.1f}s → {padded_start:.1f}s (Δ{padded_start-original_start:+.1f}s, +{self.padding}s padding)")

        return padded_start, padded_end, metadata

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

                # Check if starts after pause (for bonus in scoring)
                has_pause = i > 0 and self._has_pause_before(window_words, i)

                # Score this candidate
                score = self._score_start_candidate(
                    word['start_time'],
                    following_text,
                    original_start,
                    has_pause_before=has_pause
                )

                candidates.append({
                    'time': word['start_time'],
                    'text_preview': following_text[:50],
                    'score': score,
                    'word_index': i,
                    'has_pause': has_pause
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

    def _has_pause_before(self, words: List[Dict[str, Any]], index: int) -> bool:
        """
        Check if there's a significant pause before this word.

        Args:
            words: List of word dicts
            index: Current word index

        Returns:
            True if there's a pause >= pause_threshold before this word
        """
        if index == 0:
            return False

        prev_word = words[index - 1]
        current_word = words[index]

        # Calculate gap between previous word's end and current word's start
        prev_end = prev_word.get('end_time', 0)
        current_start = current_word.get('start_time', 0)
        gap = current_start - prev_end

        return gap >= self.pause_threshold

    def _is_sentence_start(self, words: List[Dict[str, Any]], index: int) -> bool:
        """
        Check if word at index starts a new sentence.

        Checks for:
        1. Pause detection (silence >= pause_threshold)
        2. Punctuation-based boundaries (., !, ?)
        3. Capitalization patterns

        Args:
            words: List of word dicts
            index: Current word index

        Returns:
            True if this word likely starts a sentence
        """
        if index == 0:
            return True

        # 1. Check for pause (most reliable for speech)
        if self._has_pause_before(words, index):
            return True

        prev_word = words[index - 1]['word'].strip()

        # 2. Previous word ends with sentence ender
        if any(prev_word.endswith(ender) for ender in self.sentence_enders):
            return True

        # 3. Current word is capitalized (rough heuristic)
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
        original_time: float,
        has_pause_before: bool = False
    ) -> float:
        """
        Score a candidate start time.

        Higher scores are better.

        Args:
            candidate_time: Candidate start timestamp
            following_text: Text following this start point
            original_time: Original AI-detected start time
            has_pause_before: Whether this candidate follows a natural pause

        Returns:
            Score (0-100)
        """
        score = 50.0  # Base score

        text_lower = following_text.lower()

        # 1. Pause detection bonus (+25 points) - MOST RELIABLE for speech
        if has_pause_before:
            score += 25.0

        # 2. Hook pattern bonus (+30 points max)
        for pattern in self.hook_patterns:
            if re.match(pattern, text_lower):
                score += 30.0
                break  # Only count one pattern

        # 3. Question bonus (+20 points)
        if '?' in following_text[:50]:  # Question in first ~10 words
            score += 20.0

        # 4. Proximity to original time (prefer close matches)
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

        # 5. Emotional/engaging words bonus (+10 points)
        engaging_words = ['never', 'always', 'secret', 'truth', 'shocking', 'amazing', 'incredible']
        if any(word in text_lower for word in engaging_words):
            score += 10.0

        # 6. Penalize if starting mid-sentence (detected by lowercase first letter)
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
        search_range = 5.0  # Search within 5 seconds (increased for better coverage)
        nearby_words = [
            w for w in word_timings
            if target_end - search_range <= w.get('end_time', 0) <= target_end + search_range
        ]

        if not nearby_words:
            return target_end

        # Find best end point (prefer sentence enders or pauses)
        best_end = target_end
        best_score = -1

        for i, word in enumerate(nearby_words):
            word_text = word['word'].strip()
            word_end = word.get('end_time', target_end)
            distance = abs(word_end - target_end)

            # Score this candidate end point
            score = 0

            # Prefer punctuation
            if any(word_text.endswith(ender) for ender in self.sentence_enders):
                score += 100

            # Prefer words followed by pause
            if i + 1 < len(nearby_words):
                next_word = nearby_words[i + 1]
                gap = next_word.get('start_time', 0) - word_end
                if gap >= self.pause_threshold:
                    score += 80  # High score for natural pause

            # Prefer closer to target
            proximity_score = max(0, 50 - (distance * 10))
            score += proximity_score

            if score > best_score:
                best_score = score
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
