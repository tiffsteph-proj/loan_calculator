####################################
# User Input : Loan Amount & Term  #
####################################

# Libraries
import numpy as np
import pandas as pd
from datetime import datetime

# Function to get user input
def get_user_input(loan_amount: int):
    """
    enter a valid loan amount (positive integer)
    """
    if isinstance(loan_amount, int) and loan_amount > 0:
        return loan_amount
    else:
        print("O montante deve ser um número positivo.")
        return None


# Function to calculate the user's age
def calculate_age(birthdate_str, marital_status, date_format="%d/%m/%Y"):
    """
    Calculates age from the birthdate string and determines the maximum loan term.
    For 'casado', expect birthdate_str as a tuple or list of two date strings.
    For 'solteiro', expect a single date string.

    Returns:
        max_years (int): maximum loan term allowed in years, or
        None if loan is not approved or inputs are invalid.
    """

    def calculate_individual_age(birthdate):
        today = datetime.today().date()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return age

    # For married status, expect birthdate_str to be a tuple of two birthdates
    try:
        if marital_status == "casado":
            if not (isinstance(birthdate_str, (list, tuple)) and len(birthdate_str) == 2):
                print("Para 'casado', insira duas datas de nascimento")
                return None

            birthdateA = datetime.strptime(birthdate_str[0], date_format).date()
            birthdateB = datetime.strptime(birthdate_str[1], date_format).date()
            ageA = calculate_individual_age(birthdateA)
            ageB = calculate_individual_age(birthdateB)
            age = max(ageA, ageB)

        if marital_status == "solteiro":
            birthdateA = datetime.strptime(birthdate_str, date_format).date()
            age = calculate_individual_age(birthdateA)

    except Exception:
        # Parsing error or invalid input
        return None

    if age > 75:
        print("Empréstimo não concedido.")
        return None

    # Determine the max loan term based on age
    if age <= 30:
        max_years = 40
    elif age <= 35:
        max_years = 37
    elif age > 35 and age < 40:
        max_years = 35
    else:
        max_years = 75 - age

    # Ensure max_years is at least 5 to allow minimum loan period
    if max_years < 5:
        return None

    return max_years*12
