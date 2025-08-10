# LeanEvolve

A tool for generating mathematical conjectures using Lean 4 and AI models.

## Environment Setup

### Prerequisites
- Lean 4 must be installed on your system
- Python 3.11+ with uv package manager

### Installation Steps

1. **Clone the repository with submodules**
   ```bash
   git clone --recursive git@github.com:auto-res/LeanConjecturer.git
   cd LeanConjecturer
   ```
   
   If you've already cloned without submodules:
   ```bash
   git submodule update --init --recursive
   ```

2. **Build the Lean REPL**
   ```bash
   cd repl
   lake exe cache get
   lake build
   cd ..
   ```

3. **Install Python dependencies**
   ```bash
   uv sync
   ```

## Execution Procedures

### Conjecture Generation from Multiple Files

Use the main generation script to process multiple target files:

```bash
uv run generation.py [options]
```

#### Available Options:
- `--model_name`: AI model to use for generation (default: "o3")
- `--api_key`: OpenAI API key (can be set via .env file)
- `--target`: Path to file containing target Lean files (one per line)
- `--max_iter`: Maximum number of iterations (default: 1)

#### Example:
```bash
uv run generation.py --model_name o3 --target target_files.txt --max_iter 5
```

### Conjecture Generation from Single File

For processing a single Lean file:

```bash
uv run problem_prepare.py [options]
```

#### Available Options:
- `--model_name`: AI model to use (default: "o3")
- `--api_key`: OpenAI API key (can be set via .env file)
- `--target`: Path to the target Lean file (default: "./InterClosureExercise.lean")
- `--max_iter`: Maximum number of iterations (default: 15)

#### Example:
```bash
uv run problem_prepare.py --target my_theorem.lean --max_iter 10
```

### Environment Configuration

You can set your OpenAI API key in a `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

## Execution Results

The tool generates conjectures and evaluates them using Lean 4. Results are saved in the `data/` directory:

- `conjecture.jsonl`: Generated conjectures
- `conjecture_eval_result.jsonl`: Evaluation results
- `grpo_problem.jsonl`: Non-trivial problems that couldn't be automatically proven

## Project Structure

```
LeanConjecturer/
├── src/
│   ├── application/
│   │   ├── generator/     # Conjecture generation logic
│   │   ├── evaluator/     # Conjecture evaluation logic
│   │   └── pipeline.py    # Main execution pipeline
│   ├── entity/           # Data models
│   └── constant.py       # Configuration constants
├── repl/                 # Lean 4 REPL implementation
├── data/                 # Generated results (gitignored)
├── generation.py         # Multi-file generation script
├── problem_prepare.py    # Single-file generation script
└── README.md
```

## Notes

- The `data/` directory is gitignored to avoid committing large generated files
- Make sure Lean 4 is properly installed and accessible in your PATH
- The tool requires an active internet connection for API calls to OpenAI
