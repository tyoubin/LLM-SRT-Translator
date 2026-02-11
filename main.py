import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pysrt
from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError

# Load .env file (if exists)
load_dotenv()

# ================= Configure logging =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ================= Constant definitions =================
DEFAULT_BATCH_SIZE = 10
MAX_RETRIES = 3
RETRY_DELAY = 2  # Basic retry delay (seconds)


class TranslatorConfig:
    def __init__(self, args):
        # Prioritize command line arguments, then environment variables, then defaults
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-oss:20b")

        self.input_file = Path(args.input)
        self.target_lang = args.target_lang
        self.source_lang = args.source_lang
        self.output_arg = args.output
        self.batch_size = args.batch_size
        self.bilingual = args.bilingual

        # Timeout for first request (local model loading takes time)
        self.first_timeout = 300.0
        # Timeout for subsequent requests
        self.normal_timeout = 60.0


class ProgressManager:
    """Manage checkpoint resume state"""

    def __init__(self, input_file: Path):
        self.progress_file = input_file.with_suffix(
            input_file.suffix + ".progress.json")

    def load(self):
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read progress file, will restart: {e}")
        return None

    def save(self, processed_count, output_file, translated_data):
        """Save current progress"""
        data = {
            "processed_count": processed_count,
            "output_file": str(output_file),
            # We do not save all subtitle content here, as we modify the file in real-time or save at the end
            # For simplicity, our strategy is: real-time save SRT file, progress file only records position
        }
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete(self):
        if self.progress_file.exists():
            os.remove(self.progress_file)


def generate_output_filename(input_path: Path, target_lang: str, output_arg: Optional[str] = None) -> Path:
    """
    Generate output filename:
    1. If output_arg is provided and is a directory, use input filename + target lang inside that directory.
    2. If output_arg is provided and is a file path, use it directly.
    3. If no output_arg, use input filename + target lang in the same directory as input.
    """
    # Clean special characters from language name
    clean_lang = "".join(c for c in target_lang if c.isalnum())
    default_name = f"{input_path.stem}.{clean_lang}.srt"

    if output_arg:
        out_path = Path(output_arg)
        if out_path.is_dir():
            return out_path / default_name
        return out_path

    return input_path.parent / default_name


def get_llm_client(config: TranslatorConfig):
    return OpenAI(api_key=config.api_key, base_url=config.base_url)


def build_prompt(texts: List[str], source_lang: str, target_lang: str) -> str:
    src_instruction = f" from {source_lang}" if source_lang else ""
    return (
        f"Translate the following subtitle lines{src_instruction} into {target_lang}.\n"
        "STRICT RULES:\n"
        "1. Output ONLY the translated text.\n"
        "2. Do NOT output line numbers, timestamps, or original text.\n"
        "3. Maintain the exact same number of lines as input.\n"
        "4. Keep the tone suitable for subtitles (concise).\n"
        "5. No explanations, no markdown, no quotes.\n\n"
        "Input:\n" + "\n".join(texts)
    )


def translate_batch_with_retry(client, texts, config: TranslatorConfig, is_first_run: bool):
    prompt = build_prompt(texts, config.source_lang, config.target_lang)
    retries = 0

        # Dynamically set timeout
    current_timeout = config.first_timeout if is_first_run else config.normal_timeout

    while retries <= MAX_RETRIES:
        try:
            if is_first_run:
                logger.info(f"First request, waking up model (timeout limit: {current_timeout}s)...")

            response = client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system",
                        "content": "You are a professional subtitle translator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=current_timeout
            )

            content = response.choices[0].message.content.strip()
            lines = [line.strip()
                     for line in content.split('\n') if line.strip()]
            return lines

        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            retries += 1
            wait_time = RETRY_DELAY * (2 ** (retries - 1))  # Exponential backoff
            logger.warning(
                f"API request failed ({type(e).__name__}): {e}. Retry {retries}/{MAX_RETRIES}, wait {wait_time}s...")
            if retries > MAX_RETRIES:
                raise e
            time.sleep(wait_time)

        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            raise e


def main():
    parser = argparse.ArgumentParser(description="LLM SRT subtitle translation tool (supports checkpoint resume)")
    parser.add_argument("input", help="Source SRT file path")
    parser.add_argument("--target_lang", "-t", required=True,
                        help="Target language (e.g., 'German')")
    parser.add_argument("--source_lang", "-s", help="Source language (optional, e.g., 'English')")
    parser.add_argument("--output", "-o", help="Output file path or directory (optional)")
    parser.add_argument("--batch_size", "-b", type=int,
                        default=DEFAULT_BATCH_SIZE, help="Batch size")
    parser.add_argument("--no-bilingual", dest="bilingual", action="store_false",
                        help="Do not include the original text below the translation (mono-language output)")
    parser.set_defaults(bilingual=True)

    args = parser.parse_args()
    config = TranslatorConfig(args)

    if not config.input_file.exists():
        logger.error(f"File not found: {config.input_file}")
        sys.exit(1)

    # Load subtitles
    try:
        subs = pysrt.open(str(config.input_file))
    except Exception as e:
        logger.error(f"Unable to parse SRT file: {e}")
        sys.exit(1)

    total_subs = len(subs)
    logger.info(f"Loaded {total_subs} subtitles. Target language: {config.target_lang}")

    # Check for checkpoint resume
    pm = ProgressManager(config.input_file)
    progress_data = pm.load()

    start_index = 0
    output_path = generate_output_filename(
        config.input_file, config.target_lang, config.output_arg)

    if progress_data:
        saved_count = progress_data.get("processed_count", 0)
        saved_path = progress_data.get("output_file")

        # Simple interactive confirmation
        logger.info(f"Found unfinished task progress: processed {saved_count}/{total_subs} items.")
        logger.info(f"Last output file: {saved_path}")
        user_choice = input("Continue last progress? (y/n) [y]: ").lower().strip()

        if user_choice in ('', 'y', 'yes'):
            start_index = saved_count
            output_path = Path(saved_path)
            # Load the last saved temporary file as the base to prevent overwriting
            if output_path.exists():
                subs = pysrt.open(str(output_path))
            else:
                logger.warning("Last output file was lost, will restart translation but skip marked progress.")
        else:
            logger.info("Ignored old progress, restarting.")
            pm.delete()  # Delete old progress

    client = get_llm_client(config)

    # Record start time
    is_first_batch = True

    try:
        # Main loop
        for i in range(start_index, total_subs, config.batch_size):
            batch_subs = subs[i: i + config.batch_size]
            if not batch_subs:
                break

            # Extract plain text (remove existing newlines, make single line, for LLM understanding)
            original_texts = [sub.text.replace(
                '\n', ' ') for sub in batch_subs]

            logger.info(
                f"Translating batch {i // config.batch_size + 1} (progress: {i}/{total_subs})...")

            try:
                translated_lines = translate_batch_with_retry(
                    client,
                    original_texts,
                    config,
                    is_first_run=is_first_batch
                )
                is_first_batch = False  # After first success, no longer need extended timeout
            except Exception as e:
                logger.error(f"Batch translation failed completely, program will exit. Progress saved. Error: {e}")
                sys.exit(1)

            # Length check and padding
            if len(translated_lines) != len(batch_subs):
                logger.warning(
                    f"Line count mismatch (original {len(batch_subs)} vs translated {len(translated_lines)}), padding..."
                )
                translated_lines.append("")  # Pad empty string
                translated_lines = translated_lines[:len(batch_subs)]  # Truncate excess

            # Update subtitle object (translated on top, original below, no format)
            for sub, trans_text, orig_text in zip(batch_subs, translated_lines, original_texts):
                # Ensure trans_text is not None
                trans_text = trans_text if trans_text else ""
                # Set format: include original text below translation only when bilingual output is enabled
                if config.bilingual:
                    sub.text = f"{trans_text}\n{orig_text}"
                else:
                    sub.text = trans_text

            # Save file after each batch to prevent memory loss
            subs.save(str(output_path), encoding='utf-8')

            # Update progress file
            next_index = i + len(batch_subs)
            pm.save(next_index, output_path, None)

    except KeyboardInterrupt:
        logger.warning("\nDetected user interrupt (Ctrl+C). Progress saved, can resume next run.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\nSerious error occurred: {e}")
        sys.exit(1)

    # Finished processing
    logger.info(f"Translation completed! File saved to: {output_path}")
    pm.delete()  # Task completed, delete progress file


if __name__ == "__main__":
    main()
