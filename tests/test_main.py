from types import SimpleNamespace
from pathlib import Path
import json
import sys

import pytest

# Ensure repo root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import (
    MAX_CONTEXT_LENGTH,
    RETRY_DELAY,
    generate_output_filename,
    normalize_context,
    build_prompt,
    translate_batch_with_retry,
    TranslatorConfig,
    ProgressManager,
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
)


class DummyResponse:
    def __init__(self, text):
        class Message:
            def __init__(self, content):
                self.content = content

        class Choice:
            def __init__(self, message_content):
                self.message = Message(message_content)

        self.choices = [Choice(text)]


class DummyCompletions:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def create(self, **kwargs):
        if self.call_count >= len(self.responses):
            raise RuntimeError("More calls than responses")

        current = self.responses[self.call_count]
        self.call_count += 1

        if isinstance(current, Exception):
            raise current

        return DummyResponse(current)


class DummyClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=DummyCompletions(responses))


def make_config(tmp_path, translation_context=None):
    args = SimpleNamespace(
        input=str(tmp_path / "input.srt"),
        target_lang="German",
        source_lang="English",
        output=str(tmp_path / "output.srt"),
        batch_size=5,
        bilingual=True,
        translation_context=translation_context,
    )
    return TranslatorConfig(args)


def make_rate_limit_error(message):
    response_stub = SimpleNamespace(request=SimpleNamespace(), status_code=429, headers={})
    return RateLimitError(message, response=response_stub, body=None)


def test_generate_output_filename_default():
    input_path = Path("/tmp/movie.srt")

    result = generate_output_filename(input_path, "French")

    assert result == input_path.parent / "movie.French.srt"


def test_generate_output_filename_with_directory(tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    result = generate_output_filename(tmp_path / "clip.srt", "Spanish", str(output_dir))

    assert result == output_dir / "clip.Spanish.srt"


def test_generate_output_filename_with_file(tmp_path):
    explicit = tmp_path / "final.srt"
    result = generate_output_filename(tmp_path / "clip.srt", "Korean", str(explicit))

    assert result == explicit


def test_normalize_context_none():
    assert normalize_context(None) is None
    assert normalize_context("") is None
    assert normalize_context("   ") is None


def test_normalize_context_trim_and_truncate():
    raw = "  Mix of   spaces\n\nand newlines   "
    normalized = normalize_context(raw)

    assert normalized == "Mix of spaces and newlines"

    raw_long = "a " * (MAX_CONTEXT_LENGTH + 10)
    normalized_long = normalize_context(raw_long)

    assert len(normalized_long) == MAX_CONTEXT_LENGTH
    assert not normalized_long.startswith(" ")


def test_build_prompt_includes_context_and_source():
    prompt = build_prompt(["Hello"], source_lang="English", target_lang="German", translation_context="Formal tone")

    assert "from English" in prompt
    assert "Additional translation context" in prompt
    assert "Formal tone" in prompt
    assert "STRICT RULES" in prompt
    assert "Input:\nHello" in prompt


def test_build_prompt_without_source_lang():
    prompt = build_prompt(["Hi"], source_lang="", target_lang="Spanish")

    assert "Translate the following subtitle lines from" not in prompt


def test_translate_batch_with_retry_success(tmp_path):
    config = make_config(tmp_path, translation_context="Context")
    client = DummyClient(["First translated line\nSecond translated line\n\n"])

    result = translate_batch_with_retry(client, ["Original"], config, is_first_run=True)

    assert result == ["First translated line", "Second translated line"]


def test_translate_batch_with_retry_retries(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    responses = [
        make_rate_limit_error("limit 1"),
        make_rate_limit_error("limit 2"),
        "Final line\n"
    ]
    client = DummyClient(responses)

    sleeps = []

    monkeypatch.setattr("main.time.sleep", lambda duration: sleeps.append(duration))

    result = translate_batch_with_retry(client, ["Original"], config, is_first_run=False)

    assert result == ["Final line"]
    assert sleeps == [RETRY_DELAY * (2 ** 0), RETRY_DELAY * (2 ** 1)]


def test_progress_manager_save_load_delete(tmp_path):
    input_file = tmp_path / "video.srt"
    pm = ProgressManager(input_file)

    assert pm.load() is None

    output_file = tmp_path / "translated.srt"
    pm.save(7, output_file, None)

    loaded = pm.load()
    assert loaded["processed_count"] == 7
    assert loaded["output_file"] == str(output_file)

    pm.delete()
    assert not pm.progress_file.exists()


def test_progress_manager_handles_corrupted_file(tmp_path):
    input_file = tmp_path / "video.srt"
    pm = ProgressManager(input_file)

    pm.progress_file.write_text("not json")

    assert pm.load() is None
