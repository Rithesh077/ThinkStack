# Think Stack

Think Stack is an offline, edge-AI-powered research assistant designed for local inference. It focuses on privacy, federated learning capabilities, and edge computing for researchers.

## Overview

This application provides a comprehensive suite of tools for academic literature review, running entirely on your local machine.

## Documentation Navigation

- [Features and Known Issues](docs/features.md): Overview of current capabilities and known bugs.
- [Architecture Decision Records (ADR)](docs/ADR.md): Log of major architectural and design decisions.
- [Future Scope](docs/future_scope.md): Planned features, priorities, and roadmap.

## Project Structure

- `api/`: FastAPI routes for document ingestion, search, and analysis.
- `domain/`: Core business logic (ingestion, knowledge base, search, analysis, gap finder).
- `infrastructure/`: Integrations with external systems (LLMs, Vector Store, File System).
- `desktop/`: Tauri-based desktop application (UI and LaTeX compilation).

## Getting Started

*(Instructions for setting up the backend and desktop application will be added here as the application develops)*
