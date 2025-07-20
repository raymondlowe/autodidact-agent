# Autodidact Test Suite

This folder contains all unit tests, integration tests, and demo scripts for the Autodidact Agent project.

## Structure
- `unit_test.py`: Main entry point for running all unit tests.
- Other files: Individual test scripts and demo files, moved from the project root.

## Running Tests
To run all unit tests:

```bash
python test/unit_test.py
```

## Environment Variables
Some tests require API keys for OpenAI or OpenRouter. If these are not set, those tests will be skipped and marked as such in the output.

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`

## Adding Tests
Add new test scripts to this folder and import them in `unit_test.py`.
