"""Send a single prompt to an NVIDIA OpenAI-compatible chat-completions API."""
import argparse
import base64
import mimetypes
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


MODEL = 'nvidia/nemotron-3.5-super-vl-120b-a12b'

DEFAULT_API_URL = 'https://integrate.api.nvidia.com/v1/chat/completions'
SYSTEM_PROMPT = (
    'Odgovaraj na srpskom, jasno i tačno. Pažljivo analiziraj tekst i sve '
    'priložene slike. Ako nedostaju podaci ili slika nije dovoljno jasna, '
    'navedi tu neizvesnost umesto da nagađaš. Daj sažet zaključak i kratko '
    'obrazloženje; ne izlaži skriveni tok razmišljanja.'
)
TIMEOUT_SECONDS = 60


def image_message(path):
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {'image/jpeg', 'image/png', 'image/webp'}:
        raise ValueError(f'Nepodržan format slike: {path.name} (dozvoljeni su JPEG, PNG i WebP).')
    try:
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    except OSError:
        raise ValueError(f'Sliku nije moguće pročitati: {path.name}.') from None
    return {
        'type': 'image_url',
        'image_url': {'url': f'data:{mime_type};base64,{encoded}'},
    }


def main():
    parser = argparse.ArgumentParser(description='Pošalji prompt NVIDIA AI modelu.')
    parser.add_argument(
        'prompt',
        nargs='*',
        help='Pitanje ili instrukcija za model.',
    )
    parser.add_argument(
        '--image',
        action='append',
        type=Path,
        default=[],
        metavar='PUTANJA',
        help='Lokalna JPEG, PNG ili WebP slika; opcija se može ponoviti.',
    )
    args = parser.parse_args()
    prompt = ' '.join(args.prompt).strip()
    if not prompt:
        prompt = 'Opiši priloženu sliku.' if args.image else 'Kako se zoveš?'

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

    image_parts = []
    for image_path in args.image:
        image_path = image_path.expanduser()
        if not image_path.is_file():
            print(f'Fajl slike nije pronađen: {image_path}', file=sys.stderr)
            return 1
        try:
            image_parts.append(image_message(image_path))
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
    user_content = (
        [{'type': 'text', 'text': prompt}, *image_parts]
        if image_parts else prompt
    )

    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_content},
        ],
        'temperature': 0.2,
        'max_tokens': 4096,
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
