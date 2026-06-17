# Future Scope and Planned Features

## High Priority / Architecture Goals

### 1. Feature-Specific SLMs on CPU
- Deployment of highly specialized, quantized Small Language Models (SLMs) running natively on CPU. 
- Dynamic model selection mechanism: Larger models will be selected and downloaded based on the user machine's hardware specifications (RAM/VRAM/CPU cores) to optimize local inference.

---

## Planned Features

### Priority 1: AI-Powered Research Paper Writer (LaTeX)
**Description:** The core feature for the desktop application. A pseudo-code / markdown text editor where the user writes text (e.g., "mu" or simple formulas), and the fine-tuned AI model automatically converts it into proper LaTeX code. 
- Built-in LaTeX compiler to compile the document into a PDF.
- All actions happen locally within the desktop application.

### Priority 2: Research Gap Analysis (Future Scopes / Limitations)
**Description:** Expanding the current gap analysis engine to specifically target and synthesize the "Future Work" and "Limitations" sections of *n* number of papers. 
- Will utilize specific fine-tuned models tailored for identifying promising future research scopes.

### Priority 3: Citation Visualization
**Description:** A graphical visualization of document citations. 
- Will allow users to map how different papers reference one another, highlighting foundational papers and identifying research clusters visually within the UI.
