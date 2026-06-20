# future scope and planned features

## high priority / architecture goals

### 1. feature-specific slms on cpu
- deployment of highly specialized, quantized small language models (slms) running natively on cpu/ram.
- dynamic model selection mechanism: models will be selected and downloaded based on the user machine's hardware specifications.

### 2. federated cloud fine-tuning
- outsourcing heavy model training (qlora) to cloud gpu instances.
- local federated sync client that periodically downloads tiny fine-tuned adapters (.gguf) to apply over the local frozen base model.

---

## planned features

### priority 1: ai-powered research paper writer (latex)
**description:** the core feature for the desktop application. a text editor where the user writes plain english pseudo-code or ideas, and the fine-tuned ai model converts it into proper latex code using strict gbnf grammars.
- built-in offline compiler (tectonic sidecar) to instantly compile the latex document into a pdf.
- live split-pane preview.

### priority 2: secure authorized communication (p2p sharing)
**description:** decentralized, trust-based networking using libp2p.
- allows users to securely share their local research papers, generated drafts, and analysis results with specific peers.
- utilizes public key infrastructure (pki) and digital signatures. no central server holds user data or access lists.

### priority 3: advanced gap analysis targeting future work
**description:** expanding the current gap analysis engine to specifically target and synthesize the "future work" and "limitations" sections of multiple ingested papers using cross-attention analysis.

### priority 4: citation visualization
**description:** a graphical visualization of document citations.
- will allow users to map how different papers reference one another, highlighting foundational papers and identifying research clusters visually.
