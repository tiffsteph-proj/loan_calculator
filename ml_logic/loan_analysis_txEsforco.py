####################################
# Loan Analysis : taxa de Esforço  #
####################################

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Tuple, Dict, Union, Optional
from ml_logic.calcul_loan import intCapLoanStress, intCapLoan
from ml_logic.model_IRS import process_pdf_IRS
from ml_logic.other_charge import process_pdf_CRC
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

class LoanAnalysisError(Exception):
    """Custom exception for loan analysis errors"""
    pass

def get_env_float(var_name: str, default: Optional[float] = None) -> float:
    """
    Get a float value from environment variables with proper error handling.

    Args:
        var_name: Name of the environment variable
        default: Default value if variable is not set """
    value_str = os.getenv(var_name)

    if value_str is None:
        if default is not None:
            return default
        raise LoanAnalysisError(f"{var_name} not defined in environment variables")

    try:
        return float(value_str)
    except ValueError:
        raise LoanAnalysisError(f"{var_name} must be a valid number, got: {value_str}")

def get_limit_rate() -> float:
    """Get the effort rate limit from environment variables"""
    return float(get_env_float("LIMITRATE"))


def get_monthly_loan_payment(rate: float, spread: float, loan: float, birthdate_str, marital_status: str, date_format="%d/%m/%Y") -> float:
    """Calculate monthly loan payment using actual or stress testing"""

    try:
        TXFIXA = get_env_float("TXFIXA", 0.0)

        if rate == TXFIXA:
            _, monthly_payment = intCapLoan(rate, spread, loan, birthdate_str, marital_status, date_format)

        else:
            _, monthly_payment = intCapLoanStress(rate, spread, loan, birthdate_str, marital_status, date_format)
        return monthly_payment
    except Exception as e:
        raise LoanAnalysisError(f"Erro no cálculo do empréstimo: {e}")


def get_monthly_bank_charge(pdf_path: str, verbose: bool = False):
    '''
    Extracts and sums the monthly bank charges from a PDF file.
    '''
    monthly_charge = process_pdf_CRC(pdf_path, verbose)

    try:
        # Convert list to numeric values
        monthly_values = pd.to_numeric(monthly_charge, errors='coerce')
        monthly_sum = float(monthly_values.sum())

        if verbose and monthly_sum >= 0:
            print(f"Encargos: €{monthly_sum:,.2f}")
        return monthly_sum

    except Exception as e:
        if verbose:
            print(f"⚠️ Encargos: Erro ao processar valores: {e}")
        return None


def get_total_monthly_income(pdf_path: str, verbose: bool = False) -> Dict[str, float]:
    """
    Process PDF and return total monthly income from all anexos

    Args:
        pdf_path: Path to the PDF file to process
        verbose: Enable verbose output
    """
    try:
        df_a, df_b, df_d = process_pdf_IRS(pdf_path, verbose)

        # Helper function to safely extract monthly income from dataframe
        def extract_monthly_income(df, anexo_name: str) -> float:
            if df.empty or "Mensal" not in df.columns:
                if verbose:
                    print(f"⚠️  {anexo_name}: Sem dados ou coluna 'Mensal' não encontrada")
                return 0.0

            try:
                # Convert column to numeric first, handling any string values
                monthly_values = pd.to_numeric(df["Mensal"], errors='coerce').fillna(0)
                monthly_sum = float(monthly_values.sum())

                if verbose and monthly_sum > 0:
                    print(f"📊 {anexo_name}: €{monthly_sum:,.2f}")
                return monthly_sum

            except Exception as e:
                if verbose:
                    print(f"⚠️  {anexo_name}: Erro ao processar valores: {e}")
                return 0.0

        # Extract monthly income from each anexo
        anexo_incomes = {
            "anexo_a_mensal": extract_monthly_income(df_a, "Anexo A"),
            "anexo_b_mensal": extract_monthly_income(df_b, "Anexo B"),
            "anexo_d_mensal": extract_monthly_income(df_d, "Anexo D")
        }

        # Calculate total
        total_monthly = sum(anexo_incomes.values())

        result = {
            **anexo_incomes,
            "total_mensal": total_monthly
        }

        if verbose:
            print(f"\n💰 RESUMO DE RENDIMENTOS MENSAIS:")
            print(f"   Anexo A: €{anexo_incomes['anexo_a_mensal']:,.2f}")
            print(f"   Anexo B: €{anexo_incomes['anexo_b_mensal']:,.2f}")
            print(f"   Anexo D: €{anexo_incomes['anexo_d_mensal']:,.2f}")
            print(f"   TOTAL:   €{total_monthly:,.2f}")

        return result

    except Exception as e:
        raise LoanAnalysisError("❌ Documento não aceite - Faça download de um documento mais recente")


def loan_analysis(rate: float, spread: float, loan: float, birthdate_str, marital_status: str, pdf_pathA: str, pdf_pathB: str,
    verbose: bool = False, date_format: str = "%d/%m/%Y") -> Dict[str, Union[str, float, bool, Dict]]:
    """
    Analyze the affordability

    Args:
        rate: Base interest rate
        spread: Additional spread
        loan: Loan amount
        birthdate_str: birthdate string(s)
        marital_status: Marital status string ("casado", "solteiro")
        pdf_pathA: Path to the PDF file - IRS
        pdf_pathB: Path to the PDF file - Banco de Portugal
        verbose: Enable verbose output
        date_format: Format for parsing birthdates
    """

    TXFIXA = get_env_float("TXFIXA", 0.0)
    TXSTRESS = get_env_float("TXSTRESS", 0.0)

    try:

        # Validate inputs
        if loan <= 0:
            raise LoanAnalysisError("Valor do empréstimo deve ser maior que zero")

        # Get configuration
        tx_limit = get_limit_rate()


        # Calculate monthly payment
        monthly_payment = get_monthly_loan_payment(rate, spread, loan, birthdate_str, marital_status, date_format)
        monthly_payment = float(monthly_payment)

        # Get monthly bank charges
        monthly_charges = get_monthly_bank_charge(pdf_pathB)

        # Get income breakdown (always get full breakdown for transparency)
        income_data = get_total_monthly_income(pdf_pathA, verbose)

        # Get the income
        monthly_income = float(income_data["total_mensal"])

        # Validate income
        if monthly_income <= 0:
            raise LoanAnalysisError(
                f"Rendimento mensal insuficiente para análise. "
                f"Valor encontrado: €{monthly_income:,.2f}"
            )

        # Calculate effort rate
        tx_esforco = (float(monthly_payment) + float(monthly_charges)) / float(monthly_income)

        approved = float(tx_esforco) <= float(tx_limit)


        results = {
        "Taxa Esforco": f'{tx_esforco * 100:.2f}%',
        "Mensalidade Prevista": round(monthly_payment, 2),
        "Encargos bancários": round(monthly_charges, 2),
        "Rendimento Mensal": round(monthly_income, 2),
        "Aprovação prevista": approved,
        "Mensagem": (
            f"Há possibilidade de o empréstimo ser concedido"
            if approved else
            f"Empréstimo não deverá ser aprovado - Taxa de esforço: {tx_esforco * 100:.2f}% excede o limite permitido"
        )
        }

        # Always include income breakdown for transparency
        results["detalhes_rendimento"] = {
            "Anexo A mensal": round(income_data["anexo_a_mensal"], 2),
            "Anexo B mensal": round(income_data["anexo_b_mensal"], 2),
            "Anexo D mensal": round(income_data["anexo_d_mensal"], 2),
            "Total Mensal": round(income_data["total_mensal"], 2)
        }

        # Add loan details for reference
        results["detalhes_emprestimo"] = {
            "Valor Empréstimo": round(loan, 2),
            "Taxa Base": f"{rate * 100:.3f}%",
            "Spread": f"{spread * 100:.2f}%",
            "Taxa":
                f"{(rate + spread) * 100:.3f}%"
                if rate == TXFIXA
                else f"{(float(rate) + float(spread) + TXSTRESS) * 100:.3f}%"
        }

        if verbose:
            print(f"\n📊 ANÁLISE DA TAXA DE ESFORÇO:")
            print(f"   Empréstimo: €{loan:,.2f}")
            print(f"   Mensalidade: €{monthly_payment:,.2f}")
            print(f"   Rendimento: €{monthly_income:,.2f}")
            print(f"   Taxa de Esforço: {tx_esforco * 100:.2f}% (limite: {tx_limit * 100:.1f}%)")
            print(f"   Status: {'✅ APROVADO' if approved else '❌ REJEITADO'}")

        return results

    except LoanAnalysisError:
        raise
    except Exception as e:
        raise LoanAnalysisError(f"Introduzir um estado civil válido ou corrigir as datas de nascimento")
