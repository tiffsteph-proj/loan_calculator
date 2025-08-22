####################################
#  Fixed rate - Euribor - SPREAD   #
####################################

#libraries
import numpy as np
import pandas as pd
import os
from dotenv import load_dotenv
from ml_logic.euribor import output_euriborRate


def tx_spread (rate:float,spread:float):
    """Calculate interest rate by adding spread to a fixed base or euribor."""
    load_dotenv()

    TXFIXA = float(os.getenv("TXFIXA", 0))

    euribor_data = output_euriborRate()[0]
    euribor_rates = {
        euribor_data.get('Euribor 3 meses', 0.0),
        euribor_data.get('Euribor 6 meses', 0.0),
        euribor_data.get('Euribor 12 meses', 0.0),
    }

    valid_spreads = {
        float(os.getenv("SPREAD1", 0)),
        float(os.getenv("SPREAD2", 0)),
        float(os.getenv("SPREAD3", 0)),
    }

    if rate in euribor_rates or rate == TXFIXA:
        if spread in valid_spreads:
            return rate + spread

    return ("Escolha as taxas pretendidas")
