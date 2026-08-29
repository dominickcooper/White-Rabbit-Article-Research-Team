from white_rabbit.gemini_provider import GeminiProvider


def test_retryable_rate_limit_and_server_errors():
    assert GeminiProvider._is_retryable(Exception("429 RESOURCE_EXHAUSTED rate limit"))
    assert GeminiProvider._is_retryable(Exception("503 UNAVAILABLE try again"))


def test_fatal_auth_and_bad_request_are_not_retried():
    assert not GeminiProvider._is_retryable(Exception("API key not valid"))
    assert not GeminiProvider._is_retryable(Exception("INVALID_ARGUMENT: schema mismatch"))
