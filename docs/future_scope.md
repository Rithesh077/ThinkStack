# future scope and planned features

## high priority / architecture goals

### 1. feature-specific slms on cpu
- deployment of highly specialized, quantized small language models (slms) running natively on cpu/ram.
- dynamic model selection mechanism: models will be selected and downloaded based on the user machine's hardware specifications.

### 2. federated cloud fine-tuning
- outsourcing heavy model training (qlora) to cloud gpu instances.
- local federated sync client that periodically downloads tiny fine-tuned adapters (.gguf) to apply over the local frozen base model.

---

## completed features (recent updates)

### ai-assisted research paper writer (latex)
- **description:** built-in text editor using CodeMirror where users write prompts or ideas inside a `.ths` file, and a local AI converts them in-place to compilable LaTeX.
- **compilation:** compiles instantly to PDF using the local system's `pdflatex` and provides a real-time compilation log parser for debugging LaTeX errors.
- **future enhancement:** bundle Tectonic as an offline sidecar for self-contained, zero-dependency compiling.

---

## planned features

### priority 1: secure authorized communication (p2p sharing)
**description:** decentralized, trust-based networking using libp2p.
- allows users to securely share their local research papers, generated drafts, and analysis results with specific peers.
- utilizes public key infrastructure (pki) and digital signatures. no central server holds user data or access lists.

### priority 2: advanced gap analysis targeting future work
**description:** expanding the current gap analysis engine to specifically target and synthesize the "future work" and "limitations" sections of multiple ingested papers using cross-attention analysis.

### priority 3: citation visualization
**description:** a graphical visualization of document citations.
- will allow users to map how different papers reference one another, highlighting foundational papers and identifying research clusters visually.
