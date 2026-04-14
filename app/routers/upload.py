"""
Upload router - handles PDF file uploads.
"""
import os
import hashlib
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.services import StatementService
from app.config import settings
from app.parsers import ParserFactory, AmexParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


def _serialize(obj: Any) -> Any:
    """Recursively convert dates and Decimals to JSON-serializable types."""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if hasattr(obj, '__float__'):
        return float(obj)
    return obj


def _serialize_dict(d: dict) -> dict:
    return {k: _serialize(v) for k, v in d.items()}


@router.post("/upload/preview")
async def preview_statement(
    file: UploadFile = File(..., description="Credit card statement PDF file"),
    password: str = Form(None, description="PDF password if protected"),
    bank_name: str = Form("Amex", description="Bank name (e.g., Amex)"),
    account_id: int = Form(None, description="Account ID (optional, for auto-matching)"),
    use_claude_vision: bool = Form(True, description="Use Claude AI Vision extraction"),
    extraction_model: Optional[str] = Form(None, description="Override extraction model (haiku/sonnet)"),
    use_extraction_cache: bool = Form(
        True,
        description="If true, reuse cached AI extraction for identical PDFs (same file hash)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Parse PDF and return extracted data for preview before saving.

    Tries Claude Vision extraction first (if API key configured),
    falls back to regex parser. Runs CategoryEngine on all transactions.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_content = await file.read()
    if len(file_content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )

    try:
        file_hash = hashlib.sha256(file_content).hexdigest()

        temp_dir = os.path.join(settings.upload_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.filename)

        with open(temp_path, 'wb') as f:
            f.write(file_content)

        working_file = temp_path
        if password:
            parser = AmexParser()
            try:
                working_file = parser.decrypt_pdf(temp_path, password)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to decrypt PDF: {e}")

        # ------------------------------------------------------------------
        # Extraction: Claude Vision → regex fallback
        # ------------------------------------------------------------------
        service = StatementService(db)
        extraction_method = "regex_fallback"
        extraction_meta: Dict[str, Any] = {}
        parsed_data = None

        if use_claude_vision and settings.anthropic_api_key:
            try:
                institution = await service._detect_institution(working_file, bank_name)
                parsed_data = await service._extract_with_claude_vision(
                    working_file,
                    institution,
                    file_hash=file_hash,
                    model=extraction_model,
                    use_extraction_cache=use_extraction_cache,
                )
                extraction_method = "claude_vision"
                ai_ext = parsed_data.pop("_ai_extraction", {})
                from_cache = ai_ext.get("from_cache", False)
                preflight_info = ai_ext.get("preflight") or {}
                extraction_meta = {
                    "model": ai_ext.get("model_used", "claude-haiku-4-5"),
                    "pages_processed": ai_ext.get("pages_processed", 0),
                    "pages_skipped": ai_ext.get("pages_skipped", 0),
                    "input_tokens": ai_ext.get("input_tokens", 0),
                    "output_tokens": ai_ext.get("output_tokens", 0),
                    "cost_usd": float(ai_ext.get("cost_usd", 0) or 0),
                    "confidence": float(ai_ext.get("extraction_confidence", 1.0) or 1.0),
                    "issues": ai_ext.get("issues_flagged", []),
                    "unmatched_cards": parsed_data.get("unmatched_cards", []),
                    "from_cache": from_cache,
                    "cached_at": ai_ext.get("cached_at"),
                    "original_cost_usd": float(ai_ext.get("original_cost_usd", 0) or 0),
                    "original_tokens": ai_ext.get("original_tokens", 0),
                    "preflight": {
                        "data_pages": preflight_info.get("data_pages", 0),
                        "skipped_pages": preflight_info.get("skipped_pages", 0),
                        "approx_rows": preflight_info.get("approx_rows", 0),
                        "page_summary": preflight_info.get("page_summary", []),
                        "issues": preflight_info.get("issues", []),
                    },
                }
                if from_cache:
                    logger.info(
                        f"Preview served from cache (file_hash={file_hash[:12]}…, "
                        f"saved ${extraction_meta['original_cost_usd']:.4f})"
                    )
                else:
                    logger.info(
                        f"Claude Vision preview: {extraction_meta['pages_processed']} pages, "
                        f"${extraction_meta['cost_usd']:.4f} USD"
                    )
            except Exception as e:
                logger.warning(f"Claude Vision failed in preview, falling back to regex: {e}")
                extraction_meta["fallback_reason"] = str(e)

        if parsed_data is None:
            parser = ParserFactory.get_parser(working_file, bank_name)
            parsed_data = parser.parse(working_file)
            extraction_method = "regex_fallback"

        # ------------------------------------------------------------------
        # Categorise every transaction (rules → Claude Haiku → keyword fallback)
        # ------------------------------------------------------------------
        from app.services.category_engine import CategoryEngine
        engine = CategoryEngine(db)

        for txn in parsed_data.get("transactions", []):
            # Skip if already has a user-set category (from account rules)
            if txn.get("category_source") == "user_override":
                continue

            merchant = txn.get("merchant_name") or txn.get("description_raw", "")
            country = txn.get("merchant_country") or "BD"
            try:
                cat, subcat, source, confidence = await engine.categorize(
                    merchant, txn.get("description_raw", ""), country
                )
            except Exception as ce:
                logger.warning(f"CategoryEngine failed for '{merchant}': {ce}")
                cat, subcat, source, confidence = "Other", None, "fallback", 0.5

            txn["category_ai"] = cat
            txn["subcategory_ai"] = subcat
            txn["category_source"] = source
            txn["category_confidence"] = round(confidence, 2)
            # Keep merchant_category in sync (used by preview page dropdowns & save path)
            if not txn.get("merchant_category"):
                txn["merchant_category"] = cat

        # ------------------------------------------------------------------
        # Serialize for JSON response
        # ------------------------------------------------------------------
        metadata = _serialize_dict(parsed_data["metadata"])

        transactions = []
        for txn in parsed_data.get("transactions", []):
            transactions.append(_serialize_dict(txn))

        fees = [_serialize_dict(f) for f in parsed_data.get("fees", [])]
        interest_charges = [_serialize_dict(i) for i in parsed_data.get("interest_charges", [])]

        card_sections_meta = parsed_data.get("card_sections_meta", [])

        # Use Claude-extracted bank_name if available
        effective_bank_name = bank_name
        if parsed_data and parsed_data.get("metadata", {}).get("bank_name") not in (None, "Unknown", ""):
            effective_bank_name = parsed_data["metadata"]["bank_name"]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "filename": file.filename,
                "file_hash": file_hash,
                "bank_name": effective_bank_name,
                "password": password,
                "account_id": account_id,
                "extraction_method": extraction_method,
                "extraction_meta": extraction_meta,
                "card_sections_meta": card_sections_meta,
                "metadata": metadata,
                "transactions": transactions,
                "fees": fees,
                "interest_charges": interest_charges,
                "temp_path": temp_path,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {str(e)}")


@router.post("/upload/save")
async def save_statement(
    data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Save the previewed and edited statement data to database.

    Expects the edited data from preview endpoint.
    """
    try:
        service = StatementService(db)
        result = await service.save_previewed_data(data)

        # Clean up temp file
        temp_path = data.get("temp_path")
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                # Also remove decrypted temp if exists
                decrypted_path = temp_path.replace('.pdf', '_decrypted.pdf')
                if os.path.exists(decrypted_path):
                    os.remove(decrypted_path)
            except:
                pass

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                **result
            }
        )

    except ValueError as e:
        # Clean up temp file on validation error
        temp_path = data.get("temp_path")
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                decrypted_path = temp_path.replace('.pdf', '_decrypted.pdf')
                if os.path.exists(decrypted_path):
                    os.remove(decrypted_path)
            except:
                pass
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        # Handle database constraint violations with detailed error
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        # Extract the field name from NOT NULL constraint error
        if "NOT NULL constraint failed:" in error_msg:
            field = error_msg.split("NOT NULL constraint failed:")[-1].strip()
            raise HTTPException(
                status_code=400,
                detail=f"Required field is missing: {field}\n\nThis field must be present in the PDF or provided in the form."
            )
        elif "UNIQUE constraint failed: transactions" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Duplicate transactions detected. This file contains transactions with identical:\n"
                    "  - Date\n"
                    "  - Description\n"
                    "  - Amount\n\n"
                    "This usually means:\n"
                    "  1. The same file was uploaded twice, OR\n"
                    "  2. The statement has multiple identical transactions (rare)\n\n"
                    "Check the statement list to see if this file was already processed."
                )
            )
        raise HTTPException(status_code=400, detail=f"Database constraint error: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving data: {str(e)}")


@router.post("/upload")
async def upload_statement(
    file: UploadFile = File(..., description="Credit card statement PDF file"),
    password: str = Form(None, description="PDF password if protected"),
    bank_name: str = Form("Amex", description="Bank name (e.g., Amex)"),
    account_id: int = Form(None, description="Account ID (optional)"),
    use_extraction_cache: bool = Form(
        True,
        description="If true, reuse cached AI extraction for identical PDFs",
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and process a credit card statement PDF (direct save without preview).

    - **file**: PDF file to upload
    - **password**: Optional password for encrypted PDFs
    - **bank_name**: Bank name (currently supports: Amex)

    Returns processing summary with statement ID and statistics.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )

    # Process statement
    service = StatementService(db)

    try:
        result = await service.process_statement(
            file_content=file_content,
            filename=file.filename,
            password=password,
            bank_name=bank_name,
            account_id=account_id,
            use_extraction_cache=use_extraction_cache,
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                **result
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
