"""
LLM response parsers
"""
import json
import logging

logger = logging.getLogger(__name__)


def parse_sql(response: str) -> str:
    """Extract SQL from LLM response (remove code fences and clean syntax)"""
    content = response.strip()
    logger.info(f"[parse_sql] Original response: {repr(content[:200])}")

    # Remove ```sql ... ```
    if content.startswith("```"):
        lines = content.split("```")
        if len(lines) >= 2:
            content = lines[1]
            # Remove language identifier
            if content.startswith("sql"):
                content = content[3:]
            elif content.startswith("SQL"):
                content = content[3:]

    content = content.strip()

    # Remove ALL semicolons (will add one at the end)
    content = content.replace(';', '')

    # Replace all newlines and multiple spaces with single space
    content = content.replace('\n', ' ').replace('\r', ' ')
    content = ' '.join(content.split())

    # Add single semicolon at end
    content += ';'

    logger.info(f"[parse_sql] Cleaned SQL: {repr(content[:200])}")

    return content


def parse_json(response: str) -> dict:
    """Parse JSON from LLM response with validation"""
    content = response.strip()

    # Remove ```json ... ```
    if content.startswith("```"):
        lines = content.split("```")
        if len(lines) >= 2:
            content = lines[1]
            if content.startswith("json"):
                content = content[4:]

    data = json.loads(content.strip())

    # Validate and fix questions format
    if "questions" in data:
        fixed_questions = []
        for q in data["questions"]:
            # If question is a string, skip it (LLM error)
            if isinstance(q, str):
                logger.warning(f"Skipping invalid question format: {q}")
                continue
            # If question is a dict, validate it has required fields
            if isinstance(q, dict):
                if "id" in q and "text" in q and "options" in q:
                    fixed_questions.append(q)
                else:
                    logger.warning(f"Question missing required fields: {q}")
        data["questions"] = fixed_questions

    return data
