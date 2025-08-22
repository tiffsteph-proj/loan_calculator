####################################
#    Loan : Actual // Stressed     #
####################################

import numpy as np
import pandas as pd
import numpy_financial as npf
from ml_logic.user_input import get_user_input, calculate_age
from ml_logic.interest_rate import tx_spread
from dotenv import load_dotenv
import os

#### LOAN : ACTUAL ####

def intCapLoan(rate: float, spread: float, loan: float, birthdate_str, marital_status: str, date_format="%d/%m/%Y") -> pd.DataFrame:
    # Get rate, loan and term
    total_rate = tx_spread(rate, spread)

    loan_amount = get_user_input(loan)
    if loan_amount is None:
        print("Montante do empréstimo inválido.")
        return None, None

    # Calculate loan term in months based on birthdate(s) and marital status
    term_months = calculate_age(birthdate_str, marital_status, date_format)
    if term_months is None:
        print("Prazo do empréstimo inválido com base na idade.")
        return None, None

    # Convert to monthly rate
    monthly_rate = total_rate / 12

    # Create empty DataFrame to hold schedule
    df = pd.DataFrame({
        "Nº": np.arange(1, term_months + 1)
    })

    # Calculate payment for full term
    loanActual = -npf.pmt(rate=monthly_rate, nper=term_months, pv=loan_amount)


    # Calculate interest and principal for each period
    df["Prestação mensal"] = loanActual
    df["Juros"] = df["Nº"].apply(lambda per: -npf.ipmt(rate=monthly_rate, per=per, nper=term_months, pv=loan_amount))
    df["Capital"] = df["Nº"].apply(lambda per: -npf.ppmt(rate=monthly_rate, per=per, nper=term_months, pv=loan_amount))

    # Calculate remaining capital after each payment
    df["Capital em dívida após prestação"] = round((loan_amount - df["Capital"].cumsum()),5)

    return df, loanActual


#### LOAN : STRESSED ####

def intCapLoanStress(rate: float, spread: float, loan: float, birthdate_str, marital_status: str, date_format="%d/%m/%Y") -> pd.DataFrame:
    # Get rate, loan and term

    load_dotenv()

    TXSTRESS = float(os.getenv("TXSTRESS", 0))

    try:
        total_rate = TXSTRESS + tx_spread(rate, spread)
    except Exception as e:
        raise ValueError(f"Escolha a taxa Euribor fornecida")

    loan_amount = get_user_input(loan)
    if loan_amount is None:
        print("Montante do empréstimo inválido.")
        return None, None

    term_months = calculate_age(birthdate_str, marital_status, date_format)
    if term_months is None:
        print("Prazo do empréstimo inválido com base na idade.")
        return None, None

    # Convert to monthly rate
    monthly_rate = total_rate / 12

    # Create empty DataFrame to hold schedule
    df = pd.DataFrame({
        "Nº": np.arange(1, term_months + 1)
    })

    # Calculate payment for full term
    loanStress = -npf.pmt(rate=monthly_rate, nper=term_months, pv=loan_amount)


    # Calculate interest and principal for each period
    df["Prestação mensal"] = loanStress
    df["Juros"] = df["Nº"].apply(lambda per: -npf.ipmt(rate=monthly_rate, per=per, nper=term_months, pv=loan_amount))
    df["Capital"] = df["Nº"].apply(lambda per: -npf.ppmt(rate=monthly_rate, per=per, nper=term_months, pv=loan_amount))

    # Calculate remaining capital after each payment
    df["Capital em dívida após prestação"] = round((loan_amount - df["Capital"].cumsum()),5)

    return df, loanStress
