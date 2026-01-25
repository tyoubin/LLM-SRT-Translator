# LLM SRT Translator

A command-line tool to translate SRT subtitle files using Large Language Models (LLMs).

This tool is designed for efficiently translating subtitle files, offering features like batch processing, checkpoint-based resuming, and flexible LLM backend configuration.

## Features

- **Batch Translation**: Translates subtitles in configurable batches to leverage LLM's attention, and reduce overheads.
- **Checkpoint & Resume**: Automatically saves progress and can resume from the last completed batch in case of interruptions.
- **Flexible LLM Configuration**: Supports any OpenAI-compatible API, including local models via Ollama and commercial services like OpenAI or Google.
- **Error Handling**: Implements retries with exponential backoff for common API errors.
- **Bilingual Subtitles**: The output file is formatted with the translated text on the first line and the original text on the second line for easy comparison and review.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/tyoubin/LLM-SRT-Translator
    cd LLM-SRT-Translator
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The tool is configured via environment variables. Copy the sample `.env_sample` file to `.env` and edit it with your LLM provider's details.

```bash
cp .env_sample .env
```

### Example `.env` for a local Ollama model:

```
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=gemma3:27b
```

-   `LLM_BASE_URL`: The base URL of the LLM's API endpoint.
-   `LLM_API_KEY`: Your API key for the service.
-   `LLM_MODEL`: The specific model to use for translation.

## Usage

Run the script from the command line, providing the path to your input SRT file and the target language.

```bash
python main.py -t "[Target Language] [path_to_your_file.srt]"
```

### Arguments

-   `input`: (Required) The path to the source SRT file.
-   `--target_lang`, `-t`: (Required) The target language for the translation (e.g., 'French', 'English').
-   `--source_lang`, `-s`: (Optional) The source language. If provided, it helps the model produce a more accurate translation.
-   `--batch_size`, `-b`: (Optional) The number of subtitle entries to process in each batch. Defaults to 10.

## Output Format

The output is a new SRT file with a name like `[original_name].[language].[timestamp].srt`.

Each subtitle entry in the output file is formatted to include both the translation and the original text:

## License

This project is licensed under the MIT License.
