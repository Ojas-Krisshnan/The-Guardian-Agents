"""
Document extraction and question parsing module for Synapse assessments.

Supports:
- PDF files (via pymupdf)
- DOCX files (via python-docx)
- Legacy .doc detection with clear, user-facing error guidance

Extracts questions, 4-option sets, correct answers, and concept tags without
hallucinating or inventing answer keys.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class DocumentFormatError(ValueError):
    """Raised when an unsupported or corrupted document format is encountered."""
    pass


class ExtractedQuestion(BaseModel):
    question_text: str
    options: list[str]
    correct_answer: str = ""
    concept_id: str = ""
    explanation: str = ""
    question_type: str = "multiple_choice"
    needs_review: bool = False
    warning: Optional[str] = None


class ExtractionResult(BaseModel):
    title: str = ""
    topic: str = ""
    questions: list[ExtractedQuestion]
    total_extracted: int
    warnings: list[str] = []


def extract_text_from_file(file_path: Path | str, original_filename: str = "") -> str:
    """Extract raw text from a PDF, DOCX, or text file."""
    path = Path(file_path)
    ext = (original_filename or path.name).split(".")[-1].lower()

    if ext == "doc":
        # Check if it's actually an RTF, plain text, or renamed docx
        try:
            with open(path, "rb") as f:
                header = f.read(8)
            # Zip header (PK..) means renamed docx
            if header.startswith(b"PK\x03\x04"):
                return _extract_from_docx(path)
        except Exception:
            pass
        raise DocumentFormatError(
            "Legacy .doc binary format is not supported for direct extraction. "
            "Please open your document, save or export it as .docx or .pdf, and upload again."
        )

    if ext == "pdf":
        return _extract_from_pdf(path)
    elif ext == "docx":
        return _extract_from_docx(path)
    elif ext in ("txt", "md"):
        return path.read_text(encoding="utf-8", errors="replace")
    else:
        raise DocumentFormatError(
            f"Unsupported document format '.{ext}'. Supported formats: .pdf, .docx, .doc"
        )


def _extract_from_pdf(path: Path) -> str:
    """Extract text from PDF pages using pymupdf."""
    try:
        import pymupdf  # PyMuPDF
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            raise DocumentFormatError("PDF extraction library (pymupdf) is not available on the server.")

    text_parts = []
    try:
        doc = pymupdf.open(str(path))
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
        doc.close()
    except Exception as e:
        raise DocumentFormatError(f"Failed to extract text from PDF document: {str(e)}")

    full_text = "\n\n".join(text_parts).strip()
    if not full_text:
        raise DocumentFormatError(
            "The PDF document contains no readable text. It may contain scanned images or be password-protected."
        )
    return full_text


def _extract_from_docx(path: Path) -> str:
    """Extract text from DOCX paragraphs and tables using python-docx."""
    try:
        import docx
    except ImportError:
        raise DocumentFormatError("DOCX extraction library (python-docx) is not available on the server.")

    try:
        doc = docx.Document(str(path))
        parts = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                parts.append(txt)

        # Also inspect tables if any
        for table in doc.tables:
            for row in table.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    parts.append(" | ".join(row_cells))

        full_text = "\n".join(parts).strip()
    except Exception as e:
        raise DocumentFormatError(f"Failed to extract text from DOCX document: {str(e)}")

    if not full_text:
        raise DocumentFormatError("The DOCX document is empty or contains no readable text.")
    return full_text


def parse_questions_from_text(
    text: str,
    default_title: str = "",
    default_topic: str = "",
) -> ExtractionResult:
    """
    Parse questions, 4 options (A, B, C, D), correct answers, and concept tags
    from raw document text using robust pattern recognition.
    """
    lines = [line.strip() for line in text.splitlines()]
    non_empty = [l for l in lines if l]

    extracted_title = default_title
    extracted_topic = default_topic
    warnings: list[str] = []

    # Attempt to extract title/topic from header if not provided
    if not extracted_title and non_empty:
        first_line = non_empty[0]
        title_match = re.match(r"^(?:Title|Assessment|Quiz|Exam|Test):\s*(.+)$", first_line, re.I)
        if title_match:
            extracted_title = title_match.group(1).strip()
        elif not re.match(r"^(?:Q\d|Question\s*\d|\d+[\.\)])", first_line, re.I):
            extracted_title = first_line[:80].strip()

    # Split document into question blocks
    # Common question markers:
    # "1. ", "1) ", "Q1. ", "Q1: ", "Question 1: ", "Question 1.", etc.
    q_marker_pattern = re.compile(
        r"^(?:(?:Q(?:uestion)?\s*(\d+)[:\.]?)|(\d+)[\.\)])\s*(.*)$",
        re.IGNORECASE,
    )

    blocks: list[dict] = []
    current_block: list[str] = []

    for line in lines:
        if not line:
            if current_block:
                current_block.append("")
            continue

        m = q_marker_pattern.match(line)
        if m:
            if current_block:
                blocks.append({"lines": current_block})
                current_block = []
            current_block.append(line)
        else:
            if current_block:
                current_block.append(line)

    if current_block:
        blocks.append({"lines": current_block})

    # If no blocks were split by numbered markers, attempt to look for option patterns
    if not blocks:
        blocks.append({"lines": [l for l in lines if l]})

    parsed_questions: list[ExtractedQuestion] = []

    for block_idx, block in enumerate(blocks):
        raw_lines = [l for l in block["lines"] if l]
        if not raw_lines:
            continue

        q_item = _parse_single_question_block(raw_lines, block_idx + 1, default_topic)
        if q_item:
            parsed_questions.append(q_item)

    if not parsed_questions:
        warnings.append(
            "Could not detect structured multiple-choice questions (e.g., '1. Question ... A. ... B. ... C. ... D. ...')."
        )

    return ExtractionResult(
        title=extracted_title or "Extracted Assessment",
        topic=extracted_topic,
        questions=parsed_questions,
        total_extracted=len(parsed_questions),
        warnings=warnings,
    )


def _parse_single_question_block(
    lines: list[str],
    index: int,
    default_concept: str = "",
) -> Optional[ExtractedQuestion]:
    """Parse a block of lines into an ExtractedQuestion."""
    q_text_parts: list[str] = []
    options_dict: dict[str, str] = {}
    correct_ans_raw: str = ""
    concept_raw: str = ""
    explanation_raw: str = ""

    # Option regex: matches "A. ...", "A) ...", "(A) ...", "[A] ..."
    opt_pattern = re.compile(r"^(?:(?:\(([A-Da-d])\))|(?:\[([A-Da-d])\])|(?:([A-Da-d])[\.\)]))\s*(.*)$")

    # Answer regex: matches "Answer: A", "Correct Answer: B", "Ans: C", "Answer: [text]"
    ans_pattern = re.compile(r"^(?:Correct\s+Answer|Answer|Ans):\s*(.*)$", re.IGNORECASE)

    # Concept/Topic regex: matches "Concept: ...", "Topic: ..."
    concept_pattern = re.compile(r"^(?:Concept|Topic|Tag):\s*(.*)$", re.IGNORECASE)

    # Explanation regex: matches "Explanation: ..."
    expl_pattern = re.compile(r"^(?:Explanation|Rationale):\s*(.*)$", re.IGNORECASE)

    current_opt_letter: Optional[str] = None
    collecting_question = True

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue

        # Check for answer key
        ans_m = ans_pattern.match(line_s)
        if ans_m:
            correct_ans_raw = ans_m.group(1).strip()
            collecting_question = False
            current_opt_letter = None
            continue

        # Check for concept
        concept_m = concept_pattern.match(line_s)
        if concept_m:
            concept_raw = concept_m.group(1).strip()
            collecting_question = False
            current_opt_letter = None
            continue

        # Check for explanation
        expl_m = expl_pattern.match(line_s)
        if expl_m:
            explanation_raw = expl_m.group(1).strip()
            collecting_question = False
            current_opt_letter = None
            continue

        # Check for option (A, B, C, D)
        opt_m = opt_pattern.match(line_s)
        if opt_m:
            collecting_question = False
            letter = (opt_m.group(1) or opt_m.group(2) or opt_m.group(3)).upper()
            content = opt_m.group(4).strip()
            options_dict[letter] = content
            current_opt_letter = letter
            continue

        # If we are currently collecting an option's continuation
        if current_opt_letter and not collecting_question:
            options_dict[current_opt_letter] = (options_dict[current_opt_letter] + " " + line_s).strip()
            continue

        # Otherwise, if we are still at question text
        if collecting_question:
            # Strip question numbering if present on the first line
            if not q_text_parts:
                cleaned = re.sub(r"^(?:(?:Q(?:uestion)?\s*\d+[:\.]?)|(?:\d+[\.\)]))\s*", "", line_s, flags=re.I)
                if cleaned:
                    q_text_parts.append(cleaned)
            else:
                q_text_parts.append(line_s)

    question_text = " ".join(q_text_parts).strip()
    if not question_text:
        return None

    # Collect exactly 4 options: A, B, C, D
    ordered_options: list[str] = []
    for letter in ("A", "B", "C", "D"):
        if letter in options_dict:
            ordered_options.append(options_dict[letter].strip())

    needs_review = False
    warning: Optional[str] = None

    # If fewer than 4 options detected, pad or flag
    if len(ordered_options) != 4:
        if len(options_dict) > 4:
            ordered_options = [options_dict[k].strip() for k in list(options_dict.keys())[:4]]
        else:
            while len(ordered_options) < 4:
                ordered_options.append("")
            needs_review = True
            warning = "Question does not have exactly 4 answer options."

    # Determine correct answer
    resolved_answer = ""
    if correct_ans_raw:
        ans_clean = correct_ans_raw.strip()
        letter_match = re.match(r"^([A-D])[\.\)]?$", ans_clean, re.I)
        if letter_match:
            letter_idx = ord(letter_match.group(1).upper()) - ord("A")
            if 0 <= letter_idx < len(ordered_options) and ordered_options[letter_idx]:
                resolved_answer = ordered_options[letter_idx]
        else:
            for opt in ordered_options:
                if opt and (ans_clean.lower() == opt.lower() or opt.lower() in ans_clean.lower()):
                    resolved_answer = opt
                    break

    if not resolved_answer:
        needs_review = True
        if not warning:
            warning = "No correct answer detected. Please select the correct answer before publishing."

    concept = concept_raw or default_concept or "General Concept"

    return ExtractedQuestion(
        question_text=question_text,
        options=ordered_options,
        correct_answer=resolved_answer,
        concept_id=concept,
        explanation=explanation_raw,
        needs_review=needs_review,
        warning=warning,
    )
