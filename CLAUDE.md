# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For detailed usage instructions, please refer to the [README.md](README.md) file, which contains comprehensive information about:

- Installation and setup
- Configuration options
- Usage examples and command arguments
- Output format details
- Development tips

## Quick Commands

To install dependencies:
```bash
pip install -r requirements.txt
```

To run a translation:
```bash
python main.py input.srt -t "German"
```

## Codebase Overview

The project is a single-module Python application (`main.py`) with the following key components:

1. **Configuration** – `TranslatorConfig` gathers settings from command-line arguments, then environment variables, finally defaults.
2. **Progress Management** – `ProgressManager` writes a small JSON file (`<input>.srt.progress.json`) after each batch, enabling checkpoint resume.
3. **Batch Translation** – Subtitles are processed in user-specified batches (`-b`). The program builds a prompt that lists the batch lines, sends it to the LLM via the `openai` client, and expects exactly the same number of translated lines. If the line count differs, it pads/trims.
4. **Output Formatting** – Each translated subtitle is stored as two lines: translated text first, original text second. The output file follows the pattern `<original_name>.<target_lang>.srt` unless an explicit `-o` is supplied.
5. **Retry Logic** – Each batch request is retried up to `MAX_RETRIES` (3) with exponential back-off on network/timeout errors.

The code relies on the following third-party packages:
- `pysrt` – read/write SRT files.
- `python-dotenv` – load `.env`.
- `openai` – communicate with the LLM API.

---

Generated with [Claude Code](https://claude.com/claude-code).