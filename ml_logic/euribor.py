####################################
#    Euribor - 3 / 6 / 12 Meses    #
####################################

import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Current year and month
now = datetime.now()
current_year = now.year
current_month = now.month
URL = f"https://www.euribor-rates.eu/pt/taxas-euribor-por-ano/{current_year}/"

TARGET_COLUMNS = {"Data", "Euribor 3 meses", "Euribor 6 meses", "Euribor 12 meses"}

def extract_current_month_rates(html):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='table-striped')
    if not table:
        print("Nenhum valor encontrado.")
        return []

    # Get headers
    header_cells = table.find('thead').find('tr').find_all(['th', 'td'])
    headers = []
    for cell in header_cells:
        a = cell.find('a')
        if a:
            headers.append(a.get_text(strip=True))
        else:
            headers.append(cell.get_text(strip=True) or "Data")

    # Find indexes of target columns
    selected_indexes = [i for i, h in enumerate(headers) if h in TARGET_COLUMNS]
    selected_headers = [headers[i] for i in selected_indexes]

    # Extract and filter rows
    data = []
    for row in table.find('tbody').find_all('tr'):
        cells = row.find_all(['th', 'td'])
        values = [cell.get_text(strip=True) for cell in cells]

        if len(values) != len(headers):
            continue

        date_str = values[0]
        try:
            date = datetime.strptime(date_str, "%d/%m/%Y")
            if date.year == current_year and date.month == current_month:
                filtered_row = {}
                for i in selected_indexes:
                    header = headers[i]
                    raw_value = values[i].strip().replace('%', '').replace(',', '.')

                    if header != "Data":
                        try:
                            value = round(float(raw_value) / 100, 5) # Convert to decimal
                        except ValueError:
                            value = values[i]  # fallback to original string
                    else:
                        value = values[i]
                    filtered_row[header] = value
                data.append(filtered_row)
        except ValueError:
            continue  # Skip invalid date formats
    return selected_headers, data

def fetch_current_month_rates():
    try:
        response = requests.get(URL)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Nenhum valor encontrado: {e}")
        return [], []
    return extract_current_month_rates(response.text)


def output_euriborRate():
    headers, euribor_rates = fetch_current_month_rates()

    if euribor_rates:
        data_rates = [{h: row.get(h, '') for h in headers} for row in euribor_rates]
    else:
        print("Nenhum valor encontrado.")
        data_rates = []

    return data_rates
