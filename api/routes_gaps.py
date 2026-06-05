"""
gap analysis api routes.

provides the endpoint for running comprehensive gap analysis across
ingested documents, combining claim extraction with gap detection
and research direction suggestions.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domain.knowledge_base.repository import get_chunks_by_doc_id
from domain.analysis.summarizer import summarize_single
from domain.analysis.claim_extractor import extract_claims
from domain.gap_finder.gap_analyzer import analyze_gaps
from domain.gap_finder.suggestion_engine import generate_suggestions

logger = logging.getLogger(__name__)
router = APIRouter()


class GapAnalysisRequest(BaseModel):
    """request body for gap analysis."""
    doc_ids: list[str] = Field(..., min_length=2)


@router.post("/analyze")
async def analyze(request: GapAnalysisRequest):
    """run comprehensive gap analysis across multiple documents.

    orchestrates the full gap analysis pipeline:
    1. generates summaries for each document
    2. extracts claims from each document
    3. analyzes gaps across all claims and summaries
    4. generates research direction suggestions

    requires at least 2 documents for meaningful gap analysis.

    args:
        request: list of document ids to analyze for gaps.

    returns:
        complete gap analysis with identified gaps and suggestions.
    """
    if len(request.doc_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="at least 2 documents are required for gap analysis",
        )

    summaries = []
    all_claims = []

    for doc_id in request.doc_ids:
        chunks = get_chunks_by_doc_id(doc_id)
        if not chunks["ids"]:
            logger.warning("no chunks found for document %s, skipping", doc_id)
            continue

        text = " ".join(chunks["documents"])

        summary = await summarize_single(doc_id, text)
        summaries.append({
            "doc_id": doc_id,
            "text": summary.summary_text,
        })

        doc_claims = await extract_claims(doc_id, text)
        for claim in doc_claims:
            all_claims.append({
                "doc_id": claim.doc_id,
                "text": claim.claim_text,
                "type": claim.claim_type,
            })

    if len(summaries) < 2:
        raise HTTPException(
            status_code=422,
            detail="could not process enough documents for gap analysis",
        )

    gaps = await analyze_gaps(summaries, all_claims, request.doc_ids)
    suggestions = await generate_suggestions(gaps)

    return {
        "gaps": [asdict(g) for g in gaps],
        "suggestions": [asdict(s) for s in suggestions],
        "papers_analyzed": len(summaries),
        "total_claims": len(all_claims),
        "total_gaps": len(gaps),
        "total_suggestions": len(suggestions),
    }
