"""
Stage 3: SQL Validation
Voting and validation logic for self-consistency
"""
import logging
from typing import List, Tuple
from collections import Counter
from app.dtos.query import SQLCandidate, ValidationResult

logger = logging.getLogger(__name__)


def vote_best_sql(candidates: List[SQLCandidate]) -> Tuple[SQLCandidate, int]:
    """
    Vote for best SQL using majority voting (self-consistency)

    Args:
        candidates: List of SQL candidates

    Returns:
        Tuple of (winner, vote_count)
    """
    if not candidates:
        raise ValueError("No candidates to vote on")

    # Normalize SQL for comparison (remove whitespace variations)
    normalized = {}
    for candidate in candidates:
        norm_sql = _normalize_sql(candidate.sql)
        if norm_sql not in normalized:
            normalized[norm_sql] = []
        normalized[norm_sql].append(candidate)

    # Count votes
    votes = Counter([_normalize_sql(c.sql) for c in candidates])
    winner_sql, vote_count = votes.most_common(1)[0]

    # Get original candidate (pick one with lowest temperature for determinism)
    winner_candidates = normalized[winner_sql]
    winner = min(winner_candidates, key=lambda c: c.temperature)

    logger.info(f"Vote result: {vote_count}/{len(candidates)} votes for SQL")
    logger.debug(f"Winner SQL: {winner.sql[:100]}...")

    return winner, vote_count


def validate_sql_against_rules(sql: str, validation: ValidationResult) -> bool:
    """
    Validate SQL against semantic rules

    Checks:
    1. SQL contains all "must_include" patterns
    2. SQL does not contain any "must_not" patterns

    Args:
        sql: SQL string to validate
        validation: Validation rules from LLM

    Returns:
        True if valid, False otherwise
    """
    sql_lower = sql.lower()

    # Check must_not (blocklist)
    for pattern in validation.must_not:
        pattern_lower = pattern.lower()
        if any(word in sql_lower for word in pattern_lower.split()):
            logger.warning(f"Validation failed: found forbidden pattern '{pattern}'")
            return False

    # Check must_include (allowlist) - be lenient
    missing = []
    for pattern in validation.must_include:
        pattern_lower = pattern.lower()
        # Check if ANY word from pattern is in SQL
        words = pattern_lower.split()
        if not any(word in sql_lower for word in words if len(word) > 3):
            missing.append(pattern)

    if missing:
        logger.warning(f"Validation failed: missing patterns {missing}")
        return False

    logger.info("SQL passed semantic validation")
    return True


def select_best_candidate(
    candidates: List[SQLCandidate],
    validation: ValidationResult,
    min_consensus: int = 2
) -> SQLCandidate:
    """
    Select best SQL candidate using voting + validation

    Strategy:
    1. Vote for most common SQL (self-consistency)
    2. If consensus (≥min_consensus) AND validation passes → return winner
    3. If no consensus, try each candidate against validation
    4. Fallback: return winner even if validation fails

    Args:
        candidates: List of SQL candidates
        validation: Validation rules
        min_consensus: Minimum votes needed for consensus (default: 2)

    Returns:
        Best SQL candidate
    """
    if not candidates:
        raise ValueError("No candidates provided")

    # Vote
    winner, vote_count = vote_best_sql(candidates)

    # Mark winner
    winner.confidence = vote_count / len(candidates)

    # Check if consensus reached
    has_consensus = vote_count >= min_consensus

    # Validate winner
    winner_valid = validate_sql_against_rules(winner.sql, validation)
    winner.validation_passed = winner_valid

    if has_consensus and winner_valid:
        logger.info(f"✅ High confidence: {vote_count}/{len(candidates)} consensus + validation passed")
        return winner

    if has_consensus and not winner_valid:
        logger.warning(f"⚠️ Consensus but validation failed, trying alternatives")

    # No consensus or validation failed - try other candidates
    for candidate in candidates:
        if candidate.sql == winner.sql:
            continue  # Already tried

        is_valid = validate_sql_against_rules(candidate.sql, validation)
        candidate.validation_passed = is_valid

        if is_valid:
            logger.info(f"✅ Found alternative that passes validation")
            candidate.confidence = 0.5  # Lower confidence (no consensus)
            return candidate

    # Fallback: return winner even if validation failed
    logger.warning(f"⚠️ Returning winner despite validation failure (last resort)")
    return winner


def _normalize_sql(sql: str) -> str:
    """
    Normalize SQL for comparison

    Removes:
    - Whitespace variations
    - Trailing semicolons
    - Comments

    Converts to lowercase
    """
    # Remove comments
    sql = sql.split("--")[0]  # Remove line comments

    # Normalize whitespace
    sql = " ".join(sql.split())

    # Remove trailing semicolon
    sql = sql.rstrip(";")

    # Lowercase
    sql = sql.lower()

    return sql
