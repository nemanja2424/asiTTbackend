"""Send a single prompt to an NVIDIA OpenAI-compatible chat-completions API."""
import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


MODEL = 'nvidia/nemotron-3.5-lightning-30b-a3b'

DEFAULT_API_URL = 'https://integrate.api.nvidia.com/v1/chat/completions'
SYSTEM_PROMPT = ("""
   Kako se zoves? 
""")
TIMEOUT_SECONDS = 60


def main():
    parser = argparse.ArgumentParser(description='Pošalji prompt NVIDIA AI modelu.')
    parser.add_argument(
        'prompt',
        nargs='*',
        help='Pitanje ili instrukcija; ako se izostavi, koristi se probno pitanje.',
    )
    args = parser.parse_args()
    prompt = ' '.join(args.prompt).strip() or 'Kako se zoveš?'

    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    api_key = os.getenv('NVIDIA_API_KEY', '').strip()
    api_url = os.getenv('NVIDIA_API_URL', DEFAULT_API_URL).strip()
    if not api_key:
        print(
            'Nedostaje NVIDIA_API_KEY. Podesi ga kao promenljivu okruženja '
            'ili u backend/.env.',
            file=sys.stderr,
        )
        return 1
    parsed_api_url = urlparse(api_url)
    if parsed_api_url.scheme != 'https' or not parsed_api_url.netloc:
        print('NVIDIA_API_URL mora biti validan HTTPS URL.', file=sys.stderr)
        return 1

    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
        'max_tokens': 512,
        'stream': False,
        'chat_template_kwargs': {'enable_thinking': True},
    }

    request_started = time.perf_counter()
    try:
        response = requests.post(
            api_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_duration = time.perf_counter() - request_started
    except requests.Timeout:
        print(
            f'NVIDIA API nije odgovorio u roku od {TIMEOUT_SECONDS} sekundi.',
            file=sys.stderr,
        )
        return 1
    except requests.RequestException as error:
        status = error.response.status_code if error.response is not None else None
        detail = f'HTTP status {status}.' if status is not None else type(error).__name__ + '.'
        print(f'Poziv NVIDIA API-ja nije uspeo: {detail}', file=sys.stderr)
        return 1

    try:
        result = response.json()
    except ValueError:
        print('NVIDIA API je vratio neispravan JSON odgovor.', file=sys.stderr)
        return 1

    try:
        answer = result['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        print('Odgovor NVIDIA API-ja nema očekivano polje choices[0].message.content.',
              file=sys.stderr)
        return 1
    if not isinstance(answer, str) or not answer.strip():
        print('NVIDIA API je vratio prazan tekst odgovora.', file=sys.stderr)
        return 1

    print(answer.strip())
    print(f'\nVreme odgovora LLM-a: {response_duration:.2f} s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
