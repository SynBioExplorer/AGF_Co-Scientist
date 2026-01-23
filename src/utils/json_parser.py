"""JSON parsing utilities with error handling for LLM responses"""

import json
import re
import structlog

logger = structlog.get_logger()


def parse_llm_json(response: str, agent_name: str = "Agent") -> dict:
    """Parse JSON from LLM response with robust error handling

    Args:
        response: Raw LLM response (may include markdown code blocks)
        agent_name: Name of agent for logging

    Returns:
        Parsed JSON as dictionary

    Raises:
        json.JSONDecodeError: If JSON cannot be parsed even after cleanup
    """

    # Extract JSON from response (might have markdown code blocks)
    if "```json" in response:
        json_str = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        json_str = response.split("```")[1].split("```")[0].strip()
    else:
        json_str = response.strip()

    # Try to parse JSON, with fallback for escape sequence errors
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as json_err:
        # If JSON parsing fails, try cleaning escape sequences
        logger.warning(
            f"{agent_name}: Initial JSON parse failed, attempting cleanup",
            error=str(json_err)
        )

        # Fix invalid escape sequences by escaping backslashes that aren't
        # part of valid JSON escape sequences (\", \\, \/, \b, \f, \n, \r, \t, \uXXXX)
        json_str_cleaned = re.sub(
            r'\\(?!["\\/bfnrtu])',  # Match \ not followed by valid escape char
            r'\\\\',  # Replace with \\
            json_str
        )

        try:
            data = json.loads(json_str_cleaned)
            logger.info(f"{agent_name}: JSON parsed successfully after cleanup")
            return data
        except json.JSONDecodeError as cleanup_err:
            # Log the error with context for debugging
            logger.error(
                f"{agent_name}: JSON parse failed even after cleanup",
                original_error=str(json_err),
                cleanup_error=str(cleanup_err),
                json_preview=json_str[:500]
            )
            raise cleanup_err  # Re-raise the cleanup error
