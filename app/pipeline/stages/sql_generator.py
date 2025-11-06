"""
Stage 2: SQL Generation
Generates SQL from natural language with self-consistency voting
"""
import logging
from app.pipeline.llm.client import call_llm, call_llm_async
from app.pipeline.llm.prompts import (
    build_sql_generation_prompt,
    build_sql_correction_prompt,
    build_sql_validation_prompt
)
from app.pipeline.llm.parsers import parse_sql, parse_json

logger = logging.getLogger(__name__)


def generate_sql(
    pergunta: str,
    esquema: str,
    limit: int = 100
) -> str:
    """
    Generate SQL from natural language

    Simple 3-step process:
    1. Build SQL generation prompt
    2. Call LLM
    3. Parse SQL from response

    Returns SQL string
    """
    logger.info(f"Generating SQL for: '{pergunta[:50]}...'")

    # Step 1: Build prompt
    messages = build_sql_generation_prompt(pergunta, esquema, limit)

    # Step 2: Call LLM
    response = call_llm(messages, temperature=0.1, max_tokens=800)

    # Step 3: Parse SQL
    sql = parse_sql(response)

    logger.info(f"Generated SQL: {sql[:100]}...")

    return sql


def correct_sql(
    sql_original: str,
    erro: str,
    esquema: str,
    limit: int = 100
) -> str:
    """
    Correct SQL that failed execution

    Simple 3-step process:
    1. Build correction prompt
    2. Call LLM
    3. Parse corrected SQL

    Returns corrected SQL string
    """
    logger.info("Correcting SQL after error")

    # Step 1: Build prompt
    messages = build_sql_correction_prompt(sql_original, erro, esquema, limit)

    # Step 2: Call LLM
    response = call_llm(messages, temperature=0.1, max_tokens=800)

    # Step 3: Parse SQL
    corrected_sql = parse_sql(response)

    logger.info(f"Corrected SQL: {corrected_sql[:100]}...")

    return corrected_sql


async def generate_sql_parallel(
    pergunta: str,
    esquema: str,
    limit: int = 100
) -> str:
    """
    Generate SQL with self-consistency (parallel voting)

    Generates 3 SQL candidates with different temperatures and 1 validation
    Uses voting + cross-validation to select best SQL

    Returns:
        Best SQL string (highest confidence)
    """
    import asyncio
    from app.dtos.query import SQLCandidate, ValidationResult
    from app.pipeline.stages.sql_validator import select_best_candidate

    logger.info(f"Generating SQL with self-consistency for: '{pergunta[:50]}...'")

    # Prepare prompts
    sql_prompt = build_sql_generation_prompt(pergunta, esquema, limit)
    val_prompt = build_sql_validation_prompt(pergunta, esquema)

    # Execute 4 calls in parallel
    tasks = [
        call_llm_async(sql_prompt, temperature=0.0),
        call_llm_async(sql_prompt, temperature=0.1),
        call_llm_async(sql_prompt, temperature=0.15),
        call_llm_async(val_prompt, temperature=0.2)
    ]

    results = await asyncio.gather(*tasks)

    # Parse SQL candidates
    candidates = [
        SQLCandidate(sql=parse_sql(results[0]), temperature=0.0),
        SQLCandidate(sql=parse_sql(results[1]), temperature=0.1),
        SQLCandidate(sql=parse_sql(results[2]), temperature=0.15)
    ]

    # Parse validation
    val_data = parse_json(results[3])
    validation = ValidationResult(**val_data)

    # Select best candidate
    winner = select_best_candidate(candidates, validation, min_consensus=2)

    logger.info(
        f"SQL selected: confidence={winner.confidence:.2f}, "
        f"validation_passed={winner.validation_passed}"
    )

    return winner.sql
