import re

QUESTION_STARTS = (
    "how ", "why ", "what ", "when ", "where ", "which ", "who ",
    "can ", "could ", "would ", "should ", "is ", "are ", "do ", "does "
)

COMPLAINT_WORDS = {
    "bug", "broken", "doesn't work", "does not work", "problem", "issue",
    "error", "crash", "crashes", "crashing", "wrong", "bad", "terrible",
    "hate", "annoying", "fails", "failing", "can't", "cannot",
    "isn't clear", "isnt clear", "confusing", "too much", "huge",
    "consumes a lot", "rejects", "breaks", "don't understand",
    "dont understand",
}

PRAISE_WORDS = {
    "thanks", "thank you", "great", "awesome", "amazing", "love this",
    "helpful", "excellent", "perfect", "worked perfectly", "best tutorial",
    "clear explanation", "saved me", "keep making videos like this",
}

REQUEST_PHRASES = (
    "please ", "would love", "i need help", "can you", "could you",
    "make a tutorial", "make a video", "tutorial", "guide", "walkthrough",
    "how should", "how can", "how do", "do you have",
)

SPAM_PATTERNS = (
    r"https?://",
    r"www\.",
    r"\b(?:buy now|dm me|check my channel|promo|discount|buy followers)\b",
)


def classify_comment(text: str) -> tuple[str, int, str]:
    t = (text or "").strip()
    low = t.lower()

    if not t:
        return "low_priority", 0, "Empty comment"

    if any(re.search(pattern, low) for pattern in SPAM_PATTERNS):
        return "spam", 5, "Likely promotional or link-based spam"

    is_question = "?" in t or low.startswith(QUESTION_STARTS)
    has_complaint = any(word in low for word in COMPLAINT_WORDS)
    has_praise = any(word in low for word in PRAISE_WORDS)
    has_request = any(phrase in low for phrase in REQUEST_PHRASES)

    if is_question and has_complaint:
        return "reply_now", 95, "Question plus a reported problem"

    if has_complaint:
        return "reply_now", 85, "Problem, confusion, or negative experience"

    # Praise is intentionally checked before generic request language:
    # "Please keep making videos like this" should not become an urgent task.
    if has_praise:
        return "low_priority", 25, "Positive feedback"

    if is_question:
        return "reply_now", 75, "Direct audience question"

    if has_request:
        return "reply_now", 70, "Explicit audience request"

    return "low_priority", 15, "No urgent action detected"
