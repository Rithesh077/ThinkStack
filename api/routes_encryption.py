"""
encryption api routes.

provides endpoints to encrypt papers at rest and decrypt them
on demand. encryption uses aes-256-gcm with argon2id key derivation;
the encrypted envelope (salt, nonce, kdf params, ciphertext) is stored
alongside the document metadata in the vector store so the original
full text can be recovered only with the correct password.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from domain.encryption.vault import encrypt_paper, decrypt_paper, WrongPasswordError
from domain.encryption.envelope import EnvelopeFormatError
from domain.knowledge_base.repository import (
    get_chunks_by_doc_id,
    update_chunk_metadata_field,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class EncryptRequest(BaseModel):
    doc_id: str
    password: str


class DecryptRequest(BaseModel):
    doc_id: str
    password: str


@router.post("/encrypt")
async def encrypt_document(req: EncryptRequest):
    """encrypt a document's text at rest.

    takes the full text from all chunks, encrypts it with the user's
    password, and stores the encrypted envelope string in every chunk's
    metadata under the key 'encrypted_envelope'. also sets
    'is_encrypted' = True on each chunk.

    the original chunk texts in the vector store are left intact so
    that semantic search still works -- only the *full text* is
    encrypted as an additional security layer.

    args:
        req: EncryptRequest with doc_id and password.

    returns:
        confirmation with doc_id, encrypted status, and chunk count.
    """
    chunks = get_chunks_by_doc_id(req.doc_id)
    if not chunks["ids"]:
        raise HTTPException(status_code=404, detail="document not found")

    # already encrypted?
    first_meta = chunks["metadatas"][0] if chunks["metadatas"] else {}
    is_enc = first_meta.get("is_encrypted")
    if is_enc == "true" or is_enc is True:
        raise HTTPException(status_code=409, detail="document is already encrypted")

    # reconstruct the full text to encrypt
    full_text = " ".join(chunks["documents"] or [])
    if not full_text.strip():
        raise HTTPException(status_code=422, detail="document has no text to encrypt")

    try:
        envelope_string = encrypt_paper(full_text, req.password)
    except Exception as e:
        logger.error("encryption failed for %s: %s", req.doc_id, e)
        raise HTTPException(status_code=500, detail=f"encryption failed: {e}")

    # store the envelope and flag on every chunk
    for chunk_id in chunks["ids"]:
        update_chunk_metadata_field(chunk_id, "encrypted_envelope", envelope_string)
        update_chunk_metadata_field(chunk_id, "is_encrypted", "true")

    return {
        "doc_id": req.doc_id,
        "is_encrypted": True,
        "chunks_updated": len(chunks["ids"]),
        "status": "encrypted",
    }


@router.post("/decrypt")
async def decrypt_document(req: DecryptRequest):
    """decrypt a document's encrypted envelope and return the full text.

    does NOT remove the encryption from storage -- this is a read-only
    operation that lets the user view the original text if they provide
    the correct password.

    args:
        req: DecryptRequest with doc_id and password.

    returns:
        the decrypted full text.
    """
    chunks = get_chunks_by_doc_id(req.doc_id)
    if not chunks["ids"]:
        raise HTTPException(status_code=404, detail="document not found")

    first_meta = chunks["metadatas"][0] if chunks["metadatas"] else {}
    is_enc = first_meta.get("is_encrypted")
    if not (is_enc == "true" or is_enc is True):
        raise HTTPException(status_code=400, detail="document is not encrypted")

    envelope_string = first_meta.get("encrypted_envelope")
    if not envelope_string:
        raise HTTPException(status_code=422, detail="no encrypted envelope found")

    try:
        plaintext = decrypt_paper(envelope_string, req.password)
    except WrongPasswordError:
        raise HTTPException(status_code=403, detail="incorrect password")
    except EnvelopeFormatError as e:
        raise HTTPException(status_code=422, detail=f"corrupted envelope: {e}")

    return {
        "doc_id": req.doc_id,
        "full_text": plaintext,
        "status": "decrypted",
    }


@router.post("/remove")
async def remove_encryption(req: DecryptRequest):
    """verify password and permanently remove encryption from a document.

    requires the correct password to proceed. removes the encrypted
    envelope and the is_encrypted flag from all chunk metadata.

    args:
        req: DecryptRequest with doc_id and password.

    returns:
        confirmation of encryption removal.
    """
    chunks = get_chunks_by_doc_id(req.doc_id)
    if not chunks["ids"]:
        raise HTTPException(status_code=404, detail="document not found")

    first_meta = chunks["metadatas"][0] if chunks["metadatas"] else {}
    is_enc = first_meta.get("is_encrypted")
    if not (is_enc == "true" or is_enc is True):
        raise HTTPException(status_code=400, detail="document is not encrypted")

    envelope_string = first_meta.get("encrypted_envelope")
    if not envelope_string:
        raise HTTPException(status_code=422, detail="no encrypted envelope found")

    # verify password before removing
    try:
        decrypt_paper(envelope_string, req.password)
    except WrongPasswordError:
        raise HTTPException(status_code=403, detail="incorrect password")
    except EnvelopeFormatError as e:
        raise HTTPException(status_code=422, detail=f"corrupted envelope: {e}")

    # password correct -- strip encryption metadata
    for chunk_id in chunks["ids"]:
        update_chunk_metadata_field(chunk_id, "encrypted_envelope", "")
        update_chunk_metadata_field(chunk_id, "is_encrypted", "false")

    return {
        "doc_id": req.doc_id,
        "is_encrypted": False,
        "chunks_updated": len(chunks["ids"]),
        "status": "encryption_removed",
    }
