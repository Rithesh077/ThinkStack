"""
summarizer module.

generates single-paper and multi-paper comparative summaries using
the local slm via ollama. designed for academic literature review
with structured output including key points.
"""

import json
import logging

from domain.analysis.models import Summary
from infrastructure.ollama_client import ollama_client

logger = logging.getLogger(__name__)

SINGLE_PAPER_PROMPT = """summarize the following research paper text. provide:
1. a concise summary (3-5 sentences)
2. key findings and contributions
3. methodology used
4. limitations mentioned

paper text:
{text}

respond in json format with keys: summary, key_points (list of strings), methodology, limitations."""

MULTI_PAPER_PROMPT = """you are analyzing multiple research papers on a related topic.
provide a comparative summary that covers:
1. common themes across papers
2. different approaches or methodologies used
3. areas of agreement and disagreement
4. overall state of research in this area

papers:
{papers}

respond in json format with keys: summary, key_points (list of strings), agreements, disagreements."""


async def summarize_single(doc_id: str, text: str) -> Summary:
    """generate a structured summary of a single research paper.

    sends the paper text to the slm with a structured prompt requesting
    summary, key points, methodology, and limitations.

    args:
        doc_id: the document identifier.
        text: the paper text (or concatenated chunks) to summarize.

    returns:
        populated Summary instance with extracted information.
    """
    truncated = text[:6000]
    prompt = SINGLE_PAPER_PROMPT.format(text=truncated)

    system = (
        "you are an academic research assistant specializing in "
        "literature review and paper summarization. respond only with "
        "valid json."
    )

    try:
        response = await ollama_client.generate_json(prompt, system=system)
        data = json.loads(response)
        return Summary(
            doc_ids=[doc_id],
            summary_text=data.get("summary", ""),
            key_points=data.get("key_points", []),
            summary_type="single",
        )
    except Exception as e:
        logger.error("summarization failed for %s: %s", doc_id, e)
        return Summary(
            doc_ids=[doc_id],
            summary_text=f"summarization failed: {str(e)}",
            summary_type="single",
        )


async def summarize_multiple(doc_ids: list[str], texts: dict[str, str]) -> Summary:
    """generate a comparative summary across multiple papers.

    creates a combined prompt with excerpts from each paper and asks
    the slm for a comparative analysis identifying themes, agreements,
    and disagreements.

    args:
        doc_ids: list of document identifiers being compared.
        texts: mapping of doc_id to paper text content.

    returns:
        populated Summary instance with comparative analysis.
    """
    papers_text = ""
    for i, (doc_id, text) in enumerate(texts.items()):
        excerpt = text[:2000]
        papers_text += f"\n--- paper {i + 1} (id: {doc_id}) ---\n{excerpt}\n"

    prompt = MULTI_PAPER_PROMPT.format(papers=papers_text)

    system = (
        "you are an academic research assistant specializing in "
        "comparative literature review. respond only with valid json."
    )

    try:
        response = await ollama_client.generate_json(prompt, system=system)
        data = json.loads(response)
        return Summary(
            doc_ids=doc_ids,
            summary_text=data.get("summary", ""),
            key_points=data.get("key_points", []),
            summary_type="comparative",
        )
    except Exception as e:
        logger.error("multi-paper summarization failed: %s", e)
        return Summary(
            doc_ids=doc_ids,
            summary_text=f"comparative summarization failed: {str(e)}",
            summary_type="comparative",
        )
