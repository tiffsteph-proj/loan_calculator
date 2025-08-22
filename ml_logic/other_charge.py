####################################
# Other Charge - Banco de Portugal #
####################################

import os
import re
from typing import List, Tuple
from unicodedata import normalize as unicode_normalize

import pdfplumber
from dotenv import load_dotenv
import pandas as pd


class PDFDataExtractor:
    def __init__(self, verbose: bool = False):
        """Initialize the PDF data extractor"""
        self.verbose = verbose
        self.number_pattern = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}')
        load_dotenv()

    def get_env_var(self, var_name: str) -> str:
        """Get a string environment variable with error handling"""
        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"Environment variable '{var_name}' is not set.")
        return value

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        return unicode_normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()


    def extract_matching_lines(self, pdf_path: str, search_value: str) -> list[str]:
        """
        Search the text containing the search_value.
        """
        normalized_search = self.normalize_text(search_value)
        matches = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                for line in text.splitlines():
                    if normalized_search in self.normalize_text(line):
                        matches.append(line)

        return matches


    def extract_numbers_from_lines(self, lines: list[str]) -> list[float]:
        results = []
        for line in lines:
            match = self.number_pattern.search(line)
            if match:
                value_str = match.group().replace('.', '').replace(',', '.')
                try:
                    results.append(float(value_str))
                except ValueError:
                    pass
        return results




def process_pdf_CRC(pdf_path: str, verbose: bool = False) -> Tuple[bool, List[float]]:
    """Process PDF and return whether constant env variable value was found, and extracted numbers"""
    extractor = PDFDataExtractor(verbose=verbose)

    try:
        search_value = extractor.get_env_var("BANK_CHARGE")
        matching_lines = extractor.extract_matching_lines(pdf_path,search_value)
        result = extractor.extract_numbers_from_lines(matching_lines)
        return result

    except Exception as e:
        if verbose:
            print(f"Error processing PDF: {e}")
        return None
