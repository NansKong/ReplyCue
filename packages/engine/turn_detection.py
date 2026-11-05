"""Conservative English turn endpointing using transcript cues and speech pauses."""
import re

CONTINUATIONS = {
    'and', 'or', 'but', 'with', 'for', 'to', 'the', 'a', 'an', 'if', 'because',
    'through', 'about', 'between', 'versus', 'than', 'such', 'including', 'like',
    'is', 'are', 'was', 'were', 'of', 'in', 'on', 'by', 'as', 'your',
}


def required_silence(text):
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())
    if not words or words[-1] in CONTINUATIONS or text.rstrip().endswith((',', ':', ';', '...')):
        return 1.7
    # Only take the fast path when the transcript contains a complete question.
    if len(words) >= 3 and text.rstrip().endswith('?'):
        return .7
    return 1.05
