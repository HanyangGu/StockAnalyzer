# ============================================================
# engine/llm.py -- Unified LLM Client
# ============================================================
# Single point of access for all LLM calls across the system.
#
# Currently backed by OpenAI. To switch providers:
#   1. Change only this file.
#   2. All callers (analyst, insider, news) receive the same
#      return type: str (raw text from the model).
#
# Usage:
#   from engine.llm import call_llm
#
#   result = call_llm(
#       system  = "You are a ...",
#       user    = "Classify: ...",
#       model   = "gpt-4.1-mini",     # optional, uses default if omitted
#       max_tokens = 800,             # optional
#       temperature = 0.0,            # optional
#       json_mode = True,             # optional: hints model to output JSON
#   )
#   # result is a str, or "" on failure
#
# Design notes:
#   - Returns "" on any failure so callers can handle gracefully.
#   - Callers are responsible for parsing the returned string.
#   - json_mode=True sets response_format only where supported.
#   - All errors are printed to stdout (consistent with rest of project).
# ============================================================

from openai import OpenAI

from core.config import GPT_MODEL


# ============================================================
# Default model constants
# ============================================================

# The model used for all analytical LLM calls (not the chat model).
# Cheaper/faster than the main chat model because these are
# structured classification tasks, not open-ended conversation.
LLM_ANALYSIS_MODEL      = "gpt-4.1-mini"
LLM_ANALYSIS_TEMPERATURE = 0.1


# ============================================================
# Main call function
# ============================================================

def call_llm(
    system:      str,
    user:        str,
    model:       str   = LLM_ANALYSIS_MODEL,
    max_tokens:  int   = 1000,
    temperature: float = LLM_ANALYSIS_TEMPERATURE,
    json_mode:   bool  = False,
) -> str:
    """
    Makes a single LLM call and returns the raw text response.

    Args:
        system      : System prompt string.
        user        : User message string.
        model       : Model identifier. Defaults to LLM_ANALYSIS_MODEL.
        max_tokens  : Maximum tokens to generate.
        temperature : Sampling temperature (0.0 = deterministic).
        json_mode   : If True, instructs the model to output JSON only.
                      Caller is still responsible for parsing.

    Returns:
        str : Raw model output text, or "" on any failure.
    """
    try:
        client = OpenAI()

        kwargs = dict(
            model       = model,
            max_tokens  = max_tokens,
            temperature = temperature,
            messages    = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )

        # json_mode instructs the model to output valid JSON.
        # Only set when the caller explicitly requests it and
        # the model supports the response_format parameter.
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"  LLM call error (model={model}): {e}")
        return ""
