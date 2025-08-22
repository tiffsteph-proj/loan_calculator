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
    Returns the monthly loan periods as a NumPy array.
    """
    def get_loan_term(years: int):
        return (years * 12)

    def calculate_individual_age(birthdate):
        today = datetime.today().date()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return age

    # For married status, expect birthdate_str to be a tuple of two birthdates
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


    for year in range (100): #allows 100 attempts
        try:
            selected_years = int(input(f"Escolha o prazo pretendido para o empréstimo entre 5 a {max_years} anos: "))
            if 5 <= selected_years <= max_years:
                return get_loan_term(selected_years)
            else:
                print(f"Por favor, insira um número entre 5 e {max_years}.")
        except ValueError:
            print("Entrada inválida. Insira um número inteiro.")

    print("Número máximo de tentativas atingido.")
    return None
