"""Read backend configuration fresh on demand. Never log credentials."""
import os
from pathlib import Path
from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent / '.env'

def configuration():
    # Do not inject .env into os.environ: doing so leaves stale copies after edits.
    values = dotenv_values(ENV_PATH, encoding='utf-8-sig', interpolate=False)
    def read(name, default=''):
        return str(os.environ.get(name) or values.get(name) or default).strip()
    return (read('REPLICATE_API_TOKEN'),
            read('REPLICATE_ANSWER_MODEL', 'google/gemini-2.5-flash'),
            read('GROQ_STT_MODEL', 'whisper-large-v3-turbo'),
            read('GROQ_API_KEY'))
