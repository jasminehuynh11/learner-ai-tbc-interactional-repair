"""
Document extraction utilities for Word and PDF files.
"""
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from a Word document (.docx).
    
    Args:
        file_path: Path to the .docx file
        
    Returns:
        Extracted text as a string
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx is required. Install with: pip install python-docx")
    
    doc = Document(file_path)
    text_parts = []
    
    for paragraph in doc.paragraphs:
        text_parts.append(paragraph.text)
    
    return "\n".join(text_parts)


def extract_text_from_pdf(file_path: str, extract_colors: bool = False) -> str:
    """
    Extract text from a PDF file.
    Tries pdfplumber first, falls back to PyPDF2.
    
    Args:
        file_path: Path to the .pdf file
        extract_colors: If True, returns text with color information (for pdfplumber)
        
    Returns:
        Extracted text as a string (or list of dicts with color info if extract_colors=True)
    """
    text_parts = []
    
    # Try pdfplumber first (better for formatted text and color extraction)
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    if extract_colors:
                        # Extract text with color information
                        chars = page.chars
                        text_with_colors = []
                        for char in chars:
                            text_with_colors.append({
                                'text': char['text'],
                                'color': char.get('non_stroking_color', None),
                                'size': char.get('size', None)
                            })
                        text_parts.append(text_with_colors)
                    else:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
            
            if extract_colors:
                return text_parts  # Return list of pages, each with char info
            return "\n".join(text_parts)
        except Exception as e:
            print(f"Warning: pdfplumber extraction failed: {e}")
            if extract_colors:
                # Can't extract colors with fallback
                raise Exception("Color extraction requires pdfplumber")
    
    # Fallback to PyPDF2 (no color support)
    if PYPDF2_AVAILABLE:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            return "\n".join(text_parts)
        except Exception as e:
            raise Exception(f"PDF extraction failed with both methods: {e}")
    
    raise ImportError("Either pdfplumber or PyPDF2 is required. Install with: pip install pdfplumber or pip install PyPDF2")


def extract_text_with_colors_from_pdf(file_path: str) -> list:
    """
    Extract text from PDF with color information.
    Returns list of pages, each containing list of character dictionaries.
    
    Args:
        file_path: Path to the .pdf file
        
    Returns:
        List of pages, each with character information including colors
    """
    return extract_text_from_pdf(file_path, extract_colors=True)


def extract_text(file_path: str) -> str:
    """
    Extract text from a document (Word or PDF).
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Extracted text as a string
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    suffix = file_path.suffix.lower()
    
    if suffix == '.docx':
        return extract_text_from_docx(str(file_path))
    elif suffix == '.pdf':
        return extract_text_from_pdf(str(file_path))
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .docx, .pdf")


def save_extracted_text(text: str, output_path: str) -> None:
    """
    Save extracted text to a file.
    
    Args:
        text: Text content to save
        output_path: Path where to save the text file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"Saved extracted text to: {output_path}")

