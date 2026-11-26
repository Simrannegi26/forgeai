# ForgeAI - Grounded AI Agent Evaluation Framework

ForgeAI is a Python-based framework for building, testing, and evaluating AI agents that answer questions using document-based knowledge. It focuses on grounded responses, source citations, refusal of unsupported questions, and systematic evaluation.

This project includes an HR policy assistant named **MarinerAI**, developed for the fictional company Mariner Shipping Ltd.

## 1. Project Overview

MarinerAI helps users retrieve and understand information from company policy documents.

The assistant is designed to:
- Answer questions using available policy documents.
- Provide supporting source citations and quoted evidence.
- Refuse questions that are outside the available documentation.
- Avoid unsupported assumptions and fabricated policy details.
- Support evaluation of answer quality and refusal behaviour.

## 2. System Architecture

```mermaid
flowchart TD
    A[Company Policy Documents] --> B[Document Ingestion]
    B --> C[Text Processing and Retrieval]
    C --> D[MarinerAI Agent]
    E[User Question] --> D
    D --> F{Evidence Available?}
    F -->|Yes| G[Grounded Answer]
    F -->|No| H[Refusal]
    G --> I[Source Citations]
    H --> J[Unsupported Query Response]
    K[Evaluation Dataset] --> L[Evaluation Framework]
    D --> L
    L --> M[Scorecard and Results]
```

## 3. Technology Stack

- **Language:** Python
- **AI Models:** Ollama local language models
- **Agent Framework:** Custom Python implementation
- **Configuration:** YAML
- **Data Processing:** NumPy, Pandas
- **Document Processing:** PyPDF, python-docx
- **Retrieval:** BM25-based retrieval
- **Evaluation:** Custom evaluation scripts and LLM-based judging

## 4. Project Structure

```text
forgeai/
â”‚
â”œâ”€â”€ agents/
â”œâ”€â”€ demos/
â”‚   â”œâ”€â”€ hr_policy/
â”‚   â”‚   â”œâ”€â”€ agent/
â”‚   â”‚   â”œâ”€â”€ docs/
â”‚   â”‚   â”œâ”€â”€ evals/
â”‚   â”‚   â””â”€â”€ requirements/
â”‚   â”‚
â”‚   â””â”€â”€ ship_spares/
â”‚
â”œâ”€â”€ forgeai/
â”‚   â”œâ”€â”€ agent.py
â”‚   â”œâ”€â”€ evalgen.py
â”‚   â”œâ”€â”€ generator.py
â”‚   â”œâ”€â”€ groundability.py
â”‚   â”œâ”€â”€ ingest.py
â”‚   â”œâ”€â”€ intake.py
â”‚   â”œâ”€â”€ judge.py
â”‚   â”œâ”€â”€ llm.py
â”‚   â”œâ”€â”€ optimizer.py
â”‚   â”œâ”€â”€ pipeline.py
â”‚   â”œâ”€â”€ retrieval.py
â”‚   â””â”€â”€ schemas.py
â”‚
â”œâ”€â”€ prompts/
â”œâ”€â”€ runner/
â”‚   â””â”€â”€ chat.py
â”‚
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ eval_only.py
â”‚   â””â”€â”€ make_pdfs.py
â”‚
â”œâ”€â”€ tests/
â”‚
â”œâ”€â”€ workspaces/
â”‚   â””â”€â”€ hr_frontend_test/
â”‚       â”œâ”€â”€ agent/
â”‚       â”œâ”€â”€ docs/
â”‚       â”œâ”€â”€ evals/
â”‚       â”œâ”€â”€ iterations/
â”‚       â”œâ”€â”€ requirements/
â”‚       â”œâ”€â”€ scorecard/
â”‚       â””â”€â”€ report.md
â”‚
â””â”€â”€ README.md
```

## 5. Running the HR Policy Assistant

Activate the project's virtual environment, then run:

```powershell
python -m runner.chat workspaces/hr_frontend_test/agent/agent.yaml
```

The assistant will load the configured agent and accept questions through the terminal.

Type `exit` or `quit` to stop the session.

## 6. Evaluation

The HR assistant was evaluated using a fixed dataset of 21 test cases.

### Latest evaluation results

| Metric | Result |
|---|---:|
| Overall score | 85.7% |
| Passed cases | 18/21 |
| Total test cases | 21 |
| Answerable questions | 100% |
| Out-of-scope questions | 75% |
| Edge cases | 80% |

Evaluation was performed using:

```powershell
python scripts/eval_only.py workspaces/hr_frontend_test --agent agent/agent.yaml --tag improve1
```

The evaluation-only script runs the existing test cases without regenerating the evaluation dataset or changing the agent configuration.

### Known limitations

- Some unsupported questions may be incorrectly mapped to a related policy category.
- Questions involving interpretations not explicitly stated in the documents need stricter refusal handling.
- Evaluation results are based on the current test dataset and should not be treated as proof of performance on unseen questions.
- The evaluation includes judge-based assessment, which may introduce inconsistencies.

## 7. Key Project Components

| Component | Purpose |
|---|---|
| `agent.py` | Agent execution and response generation |
| `ingest.py` | Document ingestion |
| `retrieval.py` | Document retrieval |
| `groundability.py` | Evidence and answerability checks |
| `evalgen.py` | Evaluation case generation |
| `judge.py` | Evaluation and judging |
| `optimizer.py` | Agent optimization |
| `runner/chat.py` | Interactive terminal interface |
| `scripts/eval_only.py` | Evaluation without regeneration |

## 8. Future Improvements

- Improve refusal accuracy for unsupported policy questions.
- Add more policy documents and employee categories.
- Introduce a held-out evaluation dataset.
- Improve citation verification and evidence matching.
- Develop a web-based user interface.
- Expand evaluation across additional business domains.

## 9. Project Objective

The primary objective of ForgeAI is to develop reliable, document-grounded AI agents that prioritize evidence-based responses over unsupported generation.

**Project:** ForgeAI  
**Demonstration Agent:** MarinerAI  
**Domain:** HR Policy Assistance  
**Language:** Python
