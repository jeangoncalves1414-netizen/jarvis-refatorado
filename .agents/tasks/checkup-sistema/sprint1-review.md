# SPRINT 1: Delete confirmation, web search recovery, and vision fallback

Three targeted fixes addressing user-reported failures: checklist deletion now requires confirmation before executing, web search stores compact snippets for rate-limited synthesis recovery, and vision service falls back from Groq to Gemini when the model becomes invalid. The initial implementation (commit 597a297) added the core behavior; a follow-up commit (23a24c3) tightened exception handling, added health-check on startup, and wired the fallback snippets into the recovery path.

**Watch for:** The checklist confirmation fail-safe behavior changed from fail-open to fail-closed after review feedback, meaning confirmation system failures now block deletion (likely: correct for a destructive operation, but breaks when CriticalConfirm is genuinely unavailable). Vision health-check uses a dummy API call on startup rather than validating the model name against a known list (possible: may incur latency or cost on every service init). The web search snippets are constructed but the recovery consumption path relies on regex parsing embedded JSON from tool messages (confirmed: fragile, will break if message format changes).

**Verdict**: NEEDS_CHANGES

## High-level view

Checklist delete_list now instantiates CriticalConfirm and blocks the delete when confirmation fails, switching from silent fallthrough to explicit rejection. The confirmation preview shows list title and item count.

Web search constructs a 5-result, 400-char snippet list and includes it in the ToolResult data dict. The LLM recovery synthesis extracts this via regex on the tool message content string when rate limit interrupts the normal flow, then appends formatted snippets to the recovery context.

Vision service gained a startup health-check that fires a dummy chat completion against the Groq model to detect invalid-model errors, and sets an internal flag (_groq_model_invalid) so subsequent analyze() calls skip Groq and go straight to Gemini. The analyze() and analyze_bytes() methods both check this flag before attempting Groq, and both have fallback blocks that catch model-not-found errors and retry with Gemini, marking the flag on first failure to short-circuit future attempts.

Exception handling was tightened from bare `except Exception:` to tuples of specific exceptions (ImportError, AttributeError, RuntimeError, KeyError), and the checklist confirmation failure now logs and returns an error instead of proceeding silently.

<details>
<summary>Issues (7)</summary>

1. **Fail-closed confirmation blocks legitimate use** — When CriticalConfirm import or instantiation fails (not just user denial), checklist delete is blocked entirely. This prevents deletion even when the confirmation system is broken or misconfigured. Add a fallback mode or configuration flag to allow deletions when confirmation is unavailable, or document that CriticalConfirm must be operational for delete_list to work.

2. **Health-check on every service init** — _validate_groq_model() fires a chat completion API call in __init__ whenever provider is "groq". This runs on every VisionService instantiation, adding latency and potential cost. Consider caching the validation result globally or deferring validation until first use.

3. **Regex-based snippet extraction is fragile** — _recover_synthesis in llm.py extracts fallback_snippets via regex against the string-rendered tool message content. This breaks if the JSON structure changes, if the string representation truncates, or if the field moves. Expose tool results as structured data in the recovery context instead of parsing serialized strings.

4. **Health-check uses max_tokens=1 dummy call** — The validation call to Groq sends a minimal "test" message to detect model availability. This may not exercise the vision multimodal path (image_url content type) that the actual usage requires. Consider a no-op image call, or document that the check only validates model name availability, not vision capability.

5. **Fallback snippet construction duplicates excerpt/snippet logic** — The snippet field in fallback_snippets is built as `(r.get("excerpt") or r.get("snippet") or "")[:400]`, replicating logic that likely exists elsewhere in the web search flow. Extract this into a helper function to avoid drift.

6. **Vision exception tuple may be too narrow** — analyze() and analyze_bytes() catch (ImportError, AttributeError, RuntimeError, KeyError) but the fallback trigger checks for "not found", "404", "invalid model" in the error string. API errors from Groq or Gemini (network, auth, rate limit) may raise different exception types (e.g., requests.RequestException, httpx.HTTPError) and bypass the fallback entirely. Verify what exceptions the Groq and Gemini clients actually raise for model-not-found, or widen the caught tuple.

7. **No logging when fallback snippets are missing** — If _recover_synthesis is invoked but no fallback_snippets are present (e.g., rate limit occurred on a non-web-search tool call), the recovery proceeds silently without the extra context. Add a debug log to distinguish "snippets found and used" from "snippets not available" for observability.

</details>

<details>
<summary>Details</summary>

## Checklist delete confirmation and fail-safe

The delete_list action in checklist_tool.py now requires explicit user approval before deleting a list. After resolving the target list by ID or title, the code builds a confirmation detail string with the list title and total item count (pending + completed), then instantiates CriticalConfirm and calls request(). If the user denies, the method returns `{"ok": False, "error": "Exclusão cancelada pelo usuário."}` without touching the store.

The initial implementation caught all exceptions and proceeded silently when confirmation failed. The follow-up commit changed this to catch specific exceptions (ImportError, AttributeError, RuntimeError) and return an error, blocking the deletion. This is fail-closed behavior: when the confirmation system is unavailable, deletion is prevented rather than allowed. The tradeoff is that a misconfigured or missing CriticalConfirm module makes delete_list unusable.

## Web search fallback snippets and recovery synthesis

web_search.py constructs a fallback_snippets list after the search completes but before returning the ToolResult. The list contains the first 5 results, each reduced to a dict with title[:100], url, snippet[:400], and source. The snippet field is built from r.get("excerpt") or r.get("snippet") or "", prioritizing the fuller excerpt when present.

These snippets are added to the ToolResult data dict, and base.py's model_observation() now includes "fallback_snippets" and "query" in the fields tuple, so they are serialized into the tool observation that the planner sees.

The consumption side is in llm.py's _recover_synthesis(). When a rate limit error forces synthesis recovery, the function walks backward through formatted_messages looking for tool-role messages whose content string contains "fallback_snippets". When found, it uses a regex to extract the JSON array from the string representation, parses it, and formats the snippets as a bulleted list appended to the recovery context.

This approach is fragile: it assumes the tool message content is a string containing embedded JSON, and that the "fallback_snippets" field is present as a literal substring. If model_observation() output format changes, or if the JSON is truncated or escaped differently, the regex will fail to match and the snippets will be silently ignored. A more robust approach would pass tool results as structured data to _recover_synthesis rather than reparsing serialized strings.

The regex pattern `r'"fallback_snippets":\s*(\[.*?\])'` uses a non-greedy match for the array, which may under-match if the array contains nested structures or over-match if there are multiple arrays in the content. The code wraps the parse in a try/except that swallows all exceptions, so failures are silent.

## Vision health-check and Groq→Gemini fallback

VisionService.__init__() now calls _validate_groq_model() when groq_api_key is present and provider is "groq". The validation method creates a Groq client and sends a minimal chat.completions.create() call with a "test" text message and max_tokens=1. If the call raises an exception whose string representation contains "not found", "invalid model", "404", or "model_not_found", the method logs a warning and sets self._groq_model_invalid = True.

This flag is checked at the top of analyze() and analyze_bytes() before attempting a Groq call. If the flag is set, the code switches active_provider to "gemini" and active_key to self.api_key, bypassing Groq entirely. If self.api_key is empty, it returns an error immediately.

The health-check runs on every VisionService instantiation. If the service is instantiated multiple times per session (e.g., once per tool call or once per request), the validation call will fire repeatedly, adding latency and consuming API quota. A global cache or lazy validation on first use would reduce this cost.

The dummy call uses a text-only message, not a vision multimodal message with image_url. This checks that the model name is recognized by the Groq API, but does not confirm that the model supports vision capabilities. If the model name is valid but vision is not enabled, the health-check will pass and the first analyze() call will fail with a different error.

Both analyze() and analyze_bytes() have fallback blocks that catch (ImportError, AttributeError, RuntimeError, KeyError) and check if the error string indicates a model issue. If so, they set _groq_model_invalid = True and retry with Gemini. The caught exception tuple may be too narrow: network errors, auth errors, or rate limits from the Groq client may raise different exception types and bypass the fallback entirely.

## Exception handling tightening

The follow-up commit replaced several bare `except Exception:` blocks with specific exception tuples. The vision blocks include KeyError to handle missing keys in response parsing, but do not include network-related exceptions (requests.RequestException, httpx.HTTPError, urllib3.exceptions, etc.) that the Groq or Gemini clients may raise. If a network error occurs, it will propagate uncaught and the fallback will not trigger.

## Commit metadata

Initial implementation: 597a297 (Thu Nov 12 16:03:18 2026 -0300)
Follow-up fixes: 23a24c3 (Thu Nov 12 23:05:51 2026 -0300)

</details>

<details>
<summary>File map</summary>

- **app/agent/tools/checklist_tool.py** — Added CriticalConfirm instantiation and request() call in delete_list action, changed exception handling from silent pass to logged error and blocked deletion.
- **app/agent/tools/web_search.py** — Constructed fallback_snippets list (5 results, truncated title/snippet) and added to ToolResult data dict.
- **app/agent/tools/base.py** — Added "fallback_snippets" and "query" to fields tuple in model_observation().
- **app/services/vision.py** — Added _groq_model_invalid flag, _validate_groq_model() health-check in __init__, early return in analyze()/analyze_bytes() when flag is set, fallback blocks that set the flag and retry with Gemini, API key presence check with warning on init.
- **app/services/llm.py** — Added fallback_snippets extraction via regex in _recover_synthesis(), formatted snippets appended to recovery context.

Full diff: commits 597a297 and 23a24c3 on branch main.

</details>
