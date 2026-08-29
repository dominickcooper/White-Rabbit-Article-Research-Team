from white_rabbit.web_fetch import is_blocked_source, is_grounding_redirect


def test_blocks_paywalled_hosts():
    assert is_blocked_source("https://www.tandfonline.com/doi/abs/10.1080/02684520701303881")
    assert is_blocked_source("https://content.next.westlaw.com/Document/abc")
    assert not is_blocked_source("https://vault.fbi.gov/COINTELPRO")


def test_detects_google_grounding_wrappers():
    url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHabc"
    assert is_grounding_redirect(url)
    assert not is_grounding_redirect("https://www.fbi.gov/history/famous-cases/cointelpro")
