# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

| Command | Description |
|---------|-------------|
| `pip install -r requirements.txt` | Install project dependencies. |
| `python -m pip install -e .` | (Optional) Install in editable mode for development. |
| `python main.py <input.srt> -t <language>` | Translate a subtitle file. |
| `python main.py <input.srt> -t <language> -b 1` | Translate only the first subtitle entry (useful for quick sanity checks). |
| `python main.py <input.srt> -t <language> -o <output_dir>` | Save translated file in a custom directory. |
| `python main.py <input.srt> -t <language> -o <output_file.srt>` | Override the default output filename. |
| `python main.py --help` | Show argument help. |

## Environment Configuration

The tool reads configuration from environment variables. Create a copy of `.env_sample` as `.env` and edit as needed:

```bash
cp .env_sample .env
```

Available variables:
- `LLM_BASE_URL`: Base URL of the LLM API endpoint.
- `LLM_API_KEY`: API key for the LLM service.
- `LLM_MODEL`: Name of the model to use.

If no variables are set, defaults are:
- Base URL: `http://localhost:11434/v1`
- API key: `ollama`
- Model: `gpt-oss:20b`

## High‑Level Architecture

The project is a single‑module Python application (`main.py`). Its responsibilities are:

1. **Configuration** – `TranslatorConfig` gathers settings from command‑line arguments, then environment variables, finally defaults.
2. **Progress Management** – `ProgressManager` writes a small JSON file (`<input>.srt.progress.json`) after each batch, enabling checkpoint resume.
3. **Batch Translation** – Subtitles are processed in user‑specified batches (`-b`). The program builds a prompt that lists the batch lines, sends it to the LLM via the `openai` client, and expects exactly the same number of translated lines. If the line count differs, it pads/trims.
4. **Output Formatting** – Each translated subtitle is stored as two lines: translated text first, original text second. The output file follows the pattern `<original_name>.<target_lang>.srt` unless an explicit `-o` is supplied.
5. **Retry Logic** – Each batch request is retried up to `MAX_RETRIES` (3) with exponential back‑off on network/timeout errors.

The code relies on the following third‑party packages:
- `pysrt` – read/write SRT files.
- `python-dotenv` – load `.env`.
- `openai` – communicate with the LLM API.

## Running a Single Test (Quick Check)

If you want to verify that the LLM integration works without translating an entire file, you can run a single subtitle entry:

```bash
python main.py sample.srt -t German -b 1
```

This will translate only the first subtitle, write the result to `sample.German.srt`, and exit.

## Development Tips

- **Virtual Environment** – Use `python -m venv .venv` and activate before installing dependencies.
- **Linting** – The repository does not ship a linter config, but you can add `flake8` or `ruff` if desired.
- **Testing** – No tests are included. If you add tests, run them with `python -m unittest discover`.

---

Generated with [Claude Code](https://claude.com/claude-code).