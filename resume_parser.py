import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import pdfplumber
from docx import Document
from intelligence import JobIntelligence

logger = logging.getLogger(__name__)

class ResumeParser:
    """Extracts text and structured data from resumes."""
    
    def __init__(self):
        self.intel = JobIntelligence()

    def extract_text(self, file_path: str) -> str:
        """Determines file type and extracts raw text."""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if ext == '.pdf':
            return self._extract_from_pdf(file_path)
        elif ext == '.docx':
            return self._extract_from_docx(file_path)
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _extract_from_pdf(self, file_path: str) -> str:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text.strip()

    def _extract_from_docx(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs]).strip()

    def get_structured_data(self, resume_text: str) -> Dict[str, Any]:
        """Uses Gemini (via JobIntelligence) to extract key details."""
        # For now, we'll use the intelligence layer to get search profile
        profile = self.intel.extract_search_profile(resume_text)
        return {
            "full_text": resume_text,
            "search_query": profile.get("query"),
            "location": profile.get("location")
        }
