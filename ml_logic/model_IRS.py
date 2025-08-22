####################################
#           IRS Model              #
####################################

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import pandas as pd
import pdfplumber
from unicodedata import normalize as unicode_normalize
from datetime import datetime
import os
import re
import logging


def get_env_var(var_name: str, default: Optional[float] = None) -> float:
    """
    Get a float value from environment variables with proper error handling.

    Args:
        var_name: Name of the environment variable
        default: Default value if variable is not set """
    return os.getenv(var_name)


def parse_date(text: str):
    formats = [
    "%Y-%m-%d",     # 2024-03-15
    "%d/%m/%Y",     # 15/03/2024
    "%Y/%m/%d",     # 2024/03/15
    "%d-%m-%Y",     # 15-03-2024
    "%m/%d/%Y",     # 03/15/2024 (US format)
    "%B %d, %Y",    # March 15, 2024
    "%d %B %Y",     # 15 March 2024
    "%d/%m/%y",     # 15/03/25
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    logging.warning(f"⚠️ Unable to parse date: '{text}'")
    return None


def limit_date() -> int:
    cutoff_str = get_env_var("DATE_LIMIT")

    if not cutoff_str:
        raise ValueError("DATE_LIMIT is not set")

    try:
        today = datetime.today()
        current_year = today.year
        full_date_str = f"{current_year}-{cutoff_str}"

        # Use the existing parse_date function for flexibility
        model_date = parse_date(full_date_str)

        if not model_date:
            raise ValueError(f"Could not parse constructed date: {full_date_str}")

        if today < model_date:
            cutoff_year = model_date.year - 2
        else:
            cutoff_year = model_date.year - 1

        return cutoff_year

    except Exception as e:
        raise ValueError(f"Error processing dates: {e}")


@dataclass
class AnexoConfig:
    """Configuration the different anexo"""
    key_env_var: str
    field_env_vars: List[str]
    headers: List[str]
    priority: int

    @property
    def all_env_vars(self) -> List[str]:
        return [self.key_env_var] + self.field_env_vars


class PDFDataExtractor:
    ############# STEP 1: Collect and Validate the year of the document #############
    def collect_year_by_anexo(self, pdf_path, max_header_rows=4):
        """
        Collect header rows per anexo from all pages
        """
        header_rows_by_anexo = {anexo: [] for anexo in self.ANEXO_CONFIGS}
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                anexo_type = self._determine_page_anexo_type(page_text, page_num)
                if not anexo_type:
                    continue
                tables = page.extract_tables()
                if not tables:
                    continue
                # flatten all tables from the page
                all_rows = [row for table in tables for row in table]
                # grab the first up to max_header_rows rows
                header_rows_by_anexo[anexo_type].extend(all_rows[:max_header_rows])
        return header_rows_by_anexo


    def extract_year_by_anexo(self, pdf_path, header_rows: list)-> int | None :
        """
        Given header_rows, find and return the first 4-digit year (19xx, 20xx or 21xx) found as an int.
        """
        year_re = re.compile(r"\b(19|20|21)\d{2}\b")
        header_rows_by_anexo = self.collect_year_by_anexo(pdf_path)
        years_by_anexo = {}

        for anexo, header_rows in header_rows_by_anexo.items():
            year = None
            for row in header_rows:
                for cell in row:
                    if cell:
                        match = year_re.search(str(cell))
                        if match:
                            year = int(match.group())
                            break
                if year is not None:
                    break
            years_by_anexo[anexo] = year
        return years_by_anexo


    def validate_document_year(self, pdf_path, header_rows, cutoff_year) -> Dict[str, dict]:
        """
        Validate if the extracted document year meets the cutoff requirements.
        """
        # Get cutoff year from the date limit function
        cutoff_year = limit_date()

        if cutoff_year is None:
            raise ValueError("Cutoff year is not set.")

        years_by_anexo = self.extract_year_by_anexo(pdf_path, header_rows)

        validation_anexo = {}

        for anexo_name, year in years_by_anexo.items():
            # 1: No year was captured from the document
            if year is None:
                validation_anexo[anexo_name] = {
                    "valid": False,
                    "document_year": "",
                    "reason": f"{anexo_name}: Ano dos Rendimentos não foi encontrado"
                }

            # 2: Normal validation - compare document year with cutoff
            elif year >= cutoff_year:
                validation_anexo[anexo_name] = {
                    "valid": True,
                    "document_year": year,
                    "reason": f"{anexo_name}: Documento válido"

                }
            else:
                validation_anexo[anexo_name] = {
                    "valid": False,
                    "document_year": year,
                    "reason": f"{anexo_name}: Documento não válido: {year}. Anexe por favor um documento mais recente"
                }

        return validation_anexo


    def is_document_acceptable(self,pdf_path, header_rows, cutoff_year) -> Tuple[bool, Dict[str, any]]:
        """
        Determine if the entire document should be accepted based on anexo validation
        Anexos where year is None are ignored in the validation.
        """

        validation_result = self.validate_document_year(pdf_path, header_rows, cutoff_year)
        cutoff_year = limit_date()

        # Only consider anexos where the year was found (i.e., year != NONE)
        filtered_validation = {
        anexo: v for anexo, v in validation_result.items()
        if v['document_year'] not in (None, "")
    }

        # Document is accepted only if all considered anexos are valid
        all_valid = all(v["valid"] for v in filtered_validation.values())

        # Failed anexos list
        failed_anexos = [anexo for anexo, v in filtered_validation.items() if not v["valid"]]

        # Collect the reasons
        reasons = {anexo: v["reason"] for anexo, v in filtered_validation.items()}

        validation_summary = {
        "document_accepted": all_valid,
        "anexo_results": reasons,
        "failed_anexos": failed_anexos
          }

        # Summary message
        if all_valid:
            validation_summary["summary"] = "Válido"
        else:
            anexos_list_str = ", ".join(failed_anexos)
            validation_summary["summary"] = (
                f"❌ Documento não aceite - Faça download de um documento mais recente "
                f"para os seguintes Anexos: {anexos_list_str}"
            )

        return validation_summary["summary"]


############# STEP2: Handles PDF data extraction and conversion to DataFrames #############

    # Updated Anexo B configuration to match your environment variables
    ANEXO_CONFIGS = {
        "Anexo_A": AnexoConfig(
            key_env_var="KEY_ANEXO_A",
            field_env_vars=["FIELD_VALUE_A"],
            headers=[
                "Index", "Rendimentos", "Retenções na Fonte",
                "Contribuições", "Retenções da sobretaxa", "Quotizações Sindicais"
            ],
            priority=2
        ),
        "Anexo_B": AnexoConfig(
            key_env_var="KEY_ANEXO_B",
            field_env_vars=[f"FIELD_VALUE_B_{i}_tx" for i in [
                401, 402, 403, 404, 405, 406, 407, 408, 409,
                410, 411, 412, 413, 414, 415, 416, 417, 418,
                420, 421, 451, 452, 453, 454, 455, 456, 457,
                458, 459
            ]],
            headers=["Index", "Descrição", "Código", "Taxa", "Valor"],
            priority=3
        ),
        "Anexo_D": AnexoConfig(
            key_env_var="KEY_ANEXO_D",
            field_env_vars=["FIELD_VALUE_D"],
            headers=["Index", "Valor"],
            priority=1
        ),
    }

    def __init__(self, verbose: bool = False):
        """Initialize the PDF data extractor"""
        self.verbose = verbose
        self.number_pattern = re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}')
        self.keyword_dict = self._build_keyword_dict()
        self.anexo_b_tax_rates = self._build_anexo_b_tax_rates()

        if self.verbose:
            print("🔍 DIAGNOSTIC: Keyword configuration:")
            for anexo, keywords in self.keyword_dict.items():
                print(f"  {anexo}:")
                print(f"    KEY: {repr(keywords['key'])}")
                if anexo == "Anexo_B":
                    print(f"    TAX RATES: {len(self.anexo_b_tax_rates)} codes configured")
                    print(f"    Sample rates: {dict(list(self.anexo_b_tax_rates.items())[:3])}")
                else:
                    print(f"    FIELDS: {keywords['fields'][:3]}{'...' if len(keywords['fields']) > 3 else ''}")
            print()


    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        return unicode_normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()


    def _get_env_values(self, *keys: str) -> List[str]:
        """Get non-empty environment variable values"""
        return [value for key in keys if (value := get_env_var(key))]


    def _build_anexo_b_tax_rates(self) -> Dict[str, float]:
        """Build mapping of codes to tax rates for Anexo B"""
        tax_rates = {}

        codes = [401, 402, 403, 404, 405, 406, 407, 408, 409,
                410, 411, 412, 413, 414, 415, 416, 417, 418,
                420, 421, 451, 452, 453, 454, 455, 456, 457,
                458, 459]

        for code in codes:
            env_var = f"FIELD_VALUE_B_{code}_tx"
            rate_str = get_env_var(env_var)
            if rate_str:
                try:
                    rate = float(rate_str)
                    tax_rates[str(code)] = rate
                    if self.verbose:
                        print(f"🔍 Tax rate for code {code}: {rate}")
                except ValueError:
                    if self.verbose:
                        print(f"⚠️ Invalid tax rate for code {code}: {rate_str}")

        return tax_rates

    def _build_keyword_dict(self) -> Dict[str, Dict[str, any]]:
        """Build dictionary of keywords separated by key and field values"""
        keyword_dict = {}

        for anexo_name, config in self.ANEXO_CONFIGS.items():
            key_value = get_env_var(config.key_env_var, "")

            if anexo_name == "Anexo_B":
                # For Anexo B, we don't use field keywords, we use code matching
                keyword_dict[anexo_name] = {
                    'key': key_value,
                    'fields': [],  # Empty - we use codes instead
                }
            else:
                field_values = self._get_env_values(*config.field_env_vars)
                keyword_dict[anexo_name] = {
                    'key': key_value,
                    'fields': field_values,
                }

        return keyword_dict

    def _determine_page_anexo_type(self, page_text: str, page_num: int) -> Optional[str]:
        """Determine which anexo type a page belongs to based on KEY indicators"""
        normalized_page = self.normalize_text(page_text)

        page_matches = []

        for anexo_name, keywords in self.keyword_dict.items():
            key_keyword = self.normalize_text(keywords['key'])

            if key_keyword and key_keyword in normalized_page:
                priority = self.ANEXO_CONFIGS[anexo_name].priority
                page_matches.append((priority, anexo_name))

                if self.verbose:
                    print(f"🎯 Page {page_num}: Found {anexo_name} KEY indicator: '{keywords['key'][:50]}...'")

        if not page_matches:
            if self.verbose:
                print(f"❓ Page {page_num}: No KEY indicators found")
            return None

        # Sort by priority (lower number = higher priority)
        page_matches.sort(key=lambda x: x[0])
        chosen_anexo = page_matches[0][1]

        if len(page_matches) > 1:
            competing = [name for _, name in page_matches[1:]]
            if self.verbose:
                print(f"🏆 Page {page_num}: Multiple indicators - chose {chosen_anexo} over {competing}")
        else:
            if self.verbose:
                print(f"✅ Page {page_num}: Identified as {chosen_anexo} page")

        return chosen_anexo

    def _row_matches_anexo(self, row_text: str, anexo_name: str) -> Tuple[bool, List[str]]:
        """Check if a row matches the field values for a specific anexo"""
        normalized_row = self.normalize_text(row_text)
        keywords = self.keyword_dict[anexo_name]

        if anexo_name == "Anexo_B":
            # For Anexo B, check for code patterns (401, 402, etc.)
            matched_codes = []
            for code in self.anexo_b_tax_rates.keys():
                # Look for the code in the row
                code_pattern = rf'\b{code}\b'  # Word boundary to match exact code
                if re.search(code_pattern, row_text):
                    matched_codes.append(code)

            return bool(matched_codes), matched_codes
        else:
            # Original logic for Anexo A and D
            field_keywords = [self.normalize_text(f) for f in keywords['fields']]
            field_matches = [f for f in field_keywords if f and f in normalized_row]
            return bool(field_matches), field_matches


    def extract_numbers_from_cells(self, cells: List[str]) -> List[float]:
        """Extract numbers from table cells"""
        numbers = []
        for cell in cells:
            if not cell:
                continue

            match = self.number_pattern.search(cell.strip())
            if match:
                try:
                    value_str = match.group().replace('.', '').replace(',', '.')
                    numbers.append(float(value_str))
                except ValueError:
                    continue

        return numbers


    def extract_tables_from_pdf(self, pdf_path: str) -> Dict[str, List[Tuple[int, List[List[str]]]]]:
        """Extract tables from PDF using page-level anexo identification"""
        results = {anexo: [] for anexo in self.ANEXO_CONFIGS.keys()}
        assignment_summary = {anexo: 0 for anexo in self.ANEXO_CONFIGS.keys()}
        page_types = {}

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # First pass: determine page types based on KEY indicators
                if self.verbose:
                    print("🔍 PHASE 1: Determining page types...")

                for page_num, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text() or ""
                    page_anexo_type = self._determine_page_anexo_type(page_text, page_num)
                    page_types[page_num] = page_anexo_type

                if self.verbose:
                    print(f"\n📋 PAGE TYPE SUMMARY:")
                    for page_num, anexo_type in page_types.items():
                        print(f"  Page {page_num}: {anexo_type or 'UNKNOWN'}")
                    print()

                # Second pass: extract tables and assign rows
                if self.verbose:
                    print("🔍 PHASE 2: Extracting and assigning rows...")

                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    if not tables:
                        continue

                    page_anexo_type = page_types.get(page_num)
                    if not page_anexo_type:
                        if self.verbose:
                            print(f"⏭️  Page {page_num}: Skipping - no anexo type determined")
                        continue

                    if self.verbose:
                        print(f"\n📄 Processing page {page_num} as {page_anexo_type}")

                    page_rows = []

                    for table in tables:
                        for row in table:
                            if not any(cell and cell.strip() for cell in row):
                                continue

                            row_text = " ".join(cell or "" for cell in row)
                            matches, match_details = self._row_matches_anexo(row_text, page_anexo_type)

                            if matches:
                                page_rows.append(row)
                                assignment_summary[page_anexo_type] += 1

                                if self.verbose:
                                    if page_anexo_type == "Anexo_B":
                                        print(f"  ✅ Anexo_B row matched (codes: {match_details}): {row_text[:50]}...")
                                    else:
                                        print(f"  ✅ Row matched {page_anexo_type}: {row_text[:50]}...")
                            else:
                                if self.verbose and page_anexo_type == "Anexo_B":
                                    print(f"  ⏭️  Anexo_B row skipped (no codes): {row_text[:30]}...")

                    if page_rows:
                        results[page_anexo_type].append((page_num, page_rows))
                        if self.verbose:
                            print(f"  📊 Page {page_num}: {len(page_rows)} rows assigned to {page_anexo_type}")

        except Exception as e:
            print(f"❌ Error reading PDF {pdf_path}: {e}")
            raise

        if self.verbose:
            print(f"\n📊 FINAL ASSIGNMENT SUMMARY:")
            for anexo, count in assignment_summary.items():
                print(f"  {anexo}: {count} rows")
            print()

        return results


    def _process_anexo_a(self, page: int, rows: List[List[str]]) -> List[Dict]:
        """Process Anexo A specific data and validate document year"""

        processed_rows = []

        for row in rows:
            values = self.extract_numbers_from_cells(row)
            if len(values) < 1:
                continue

            row_dict = {"Index": f"Page_{page}"}
            headers = self.ANEXO_CONFIGS["Anexo_A"].headers[1:]

            for i, header in enumerate(headers):
                row_dict[header] = values[i] if i < len(values) else 0.0

            processed_rows.append(row_dict)

        return processed_rows


    def _process_anexo_b(self, page: int, rows: List[List[str]]) -> List[Dict]:
        """Process Anexo B specific data with code and tax rate extraction and validate document year"""

        processed_rows = []

        if self.verbose:
            print(f"    🔍 Processing {len(rows)} Anexo_B rows on page {page}")

        for i, row in enumerate(rows):
            if self.verbose:
                print(f"      Row {i+1}: {row}")

            row_text = " ".join(cell or "" for cell in row)

            # Find the code in this row
            found_code = None
            for code in self.anexo_b_tax_rates.keys():
                if re.search(rf'\b{code}\b', row_text):
                    found_code = code
                    break

            if not found_code:
                if self.verbose:
                    print(f"        ❌ No valid code found in row")
                continue

            # Get the tax rate for this code
            tax_rate = self.anexo_b_tax_rates.get(found_code, 0.0)

            # Extract description and value
            desc = ""
            valor = 0.0

            if len(row) >= 1:
                desc = (row[0] or "").strip()

            # Extract numeric values from the row
            values = self.extract_numbers_from_cells(row)
            if values:
                valor = values[0]  # Take the first numeric value found

            row_dict = {
                "Index": f"Page_{page}",
                "Descrição": desc,
                "Código": found_code,
                "Taxa": tax_rate,
                "Valor": valor
            }

            processed_rows.append(row_dict)

            if self.verbose:
                print(f"        ✅ Processed: Code={found_code}, Taxa={tax_rate}, Valor={valor}")

        if self.verbose:
            print(f"    📊 Anexo_B page {page}: {len(processed_rows)} processed rows")

        return processed_rows


    def _process_anexo_d(self, page: int, rows: List[List[str]]) -> List[Dict]:
        """Process Anexo D specific data and validate document year"""

        processed_rows = []

        for row in rows:
            val_numbers = self.extract_numbers_from_cells(row)
            if not val_numbers:
                continue

            row_dict = {
                "Index": f"Page_{page}",
                "Valor": val_numbers[0]
            }
            processed_rows.append(row_dict)

        return processed_rows

    def _create_anexo_a_dataframe(self, data: List[Dict]) -> pd.DataFrame:
        """Create and enhance Anexo A DataFrame"""
        headers = self.ANEXO_CONFIGS["Anexo_A"].headers
        if not data:
            return pd.DataFrame(columns=headers + ["Total", "Mensal"])

        df = pd.DataFrame(data)

        # Ensure numeric columns
        numeric_cols = headers[1:]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Calculate derived fields
        df["Total"] = (
            df.get("Rendimentos", 0) - df.get("Retenções na Fonte", 0) -
            df.get("Contribuições", 0) - df.get("Retenções da sobretaxa", 0) -
            df.get("Quotizações Sindicais", 0)
        )
        df["Mensal"] = df["Total"] / 12

        return df

    def _create_anexo_b_dataframe(self, data: List[Dict]) -> pd.DataFrame:
        """Create Anexo B DataFrame with proper structure"""
        headers = self.ANEXO_CONFIGS["Anexo_B"].headers
        if not data:
            return pd.DataFrame(columns=headers)

        df = pd.DataFrame(data)

        # Ensure numeric columns
        if "Taxa" in df.columns:
            df["Taxa"] = pd.to_numeric(df["Taxa"], errors='coerce').fillna(0)
        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0)

        # Calculate derived fields
        df["Total"] = df.get("Taxa", 0) * df.get("Valor", 0)
        df["Mensal"] = df.get("Total", 0) / 12


        # Add summary row with totals
        if not df.empty:
            total_valor = df["Valor"].sum()
            total_rate = df["Total"].sum()
            total_mensal = df["Mensal"].sum()

            summary_anexoB = pd.DataFrame({
            "Index": ["TOTAL ANEXO B"],
            "Descrição": [""],
            "Código": [""],
            "Taxa": [0], # average impossible. each code has a specific rate
            "Valor": [total_valor],
            "Total": [total_rate],
            "Mensal": [total_mensal]
        })

        return summary_anexoB

    def _create_anexo_d_dataframe(self, data: List[Dict]) -> pd.DataFrame:
        """Create Anexo D DataFrame"""
        headers = self.ANEXO_CONFIGS["Anexo_D"].headers
        if not data:
            return pd.DataFrame(columns=headers)

        df = pd.DataFrame(data)

        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0)

        # Calculate derived fields
        df["Mensal"] = df.get("Valor", 0) / 12


        # Add summary row with totals
        if not df.empty:
            total_valor = df["Valor"].sum()
            total_mensal = df["Mensal"].sum()

            summary_anexoD = pd.DataFrame({
            "Index": ["TOTAL ANEXO D"],
            "Valor": [total_valor],
            "Mensal": [total_mensal]
        })

        return summary_anexoD

    def convert_to_dataframes(
        self,
        tables_by_anexo: Dict[str, List[Tuple[int, List[List[str]]]]],
        fill_none: bool = True
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Convert extracted tables to DataFrames"""

        if not any(tables_by_anexo.values()):
            print("ℹ️ No annexes found")
            empty_dfs = tuple(
                pd.DataFrame(columns=config.headers)
                for config in self.ANEXO_CONFIGS.values()
            )
            return empty_dfs

        anexo_data = {"Anexo_A": [], "Anexo_B": [], "Anexo_D": []}
        processors = {
            "Anexo_A": self._process_anexo_a,
            "Anexo_B": self._process_anexo_b,
            "Anexo_D": self._process_anexo_d
        }

        for anexo_name, page_data_list in tables_by_anexo.items():
            if not page_data_list or anexo_name not in processors:
                continue

            try:
                for page, rows in page_data_list:
                    processed_data = processors[anexo_name](page, rows)
                    anexo_data[anexo_name].extend(processed_data)

                    if self.verbose:
                        print(f"📝 {anexo_name} page {page}: processed {len(processed_data)} rows")

            except Exception as e:
                print(f"⚠️ Error processing {anexo_name}: {e}")

        # Create DataFrames with specific handling for each type
        df_anexo_a = self._create_anexo_a_dataframe(anexo_data["Anexo_A"])
        df_anexo_b = self._create_anexo_b_dataframe(anexo_data["Anexo_B"])
        df_anexo_d = self._create_anexo_d_dataframe(anexo_data["Anexo_D"])

        if fill_none:
            for df in [df_anexo_a, df_anexo_b, df_anexo_d]:
                df.fillna('', inplace=True)

        if self.verbose:
            print(f"\n📋 FINAL DATAFRAMES:")
            print(f"  Anexo_A: {len(df_anexo_a)} rows")
            print(f"  Anexo_B: {len(df_anexo_b)} rows")
            print(f"  Anexo_D: {len(df_anexo_d)} rows")

        return df_anexo_a, df_anexo_b, df_anexo_d


# Process the PDF document
def process_pdf_IRS(pdf_path: str, verbose: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool, dict]:
    """Main function to process PDF and return DataFrames with validation results"""

    extractor = PDFDataExtractor(verbose=verbose)
    cutoff_year = limit_date()

    # Get the validation of the documents
    header_rows = extractor.collect_year_by_anexo(pdf_path)
    year_by_anexo = extractor.extract_year_by_anexo(pdf_path,header_rows)
    result = extractor.validate_document_year(pdf_path, year_by_anexo, cutoff_year=cutoff_year)
    validation_summary = extractor.is_document_acceptable(pdf_path, result, cutoff_year=cutoff_year)

    if validation_summary == "Válido":
        # Get the data
        tables_by_anexo = extractor.extract_tables_from_pdf(pdf_path)
        dataframes = extractor.convert_to_dataframes(tables_by_anexo)

        return dataframes[0], dataframes[1], dataframes[2]


    else:
        return validation_summary
