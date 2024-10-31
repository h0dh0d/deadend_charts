import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime, timedelta
import time
import os

# List of currencies
currencies = [
    'usd', 'eur', 'gbp', 'chf', 'cad', 'aud', 'sek', 'nok', 'rub', 'thb', 'sgd', 'hkd', 'azn', 'amd',
    'dkk', 'aed', 'jpy', 'try', 'cny', 'sar', 'inr', 'myr', 'afn', 'kwd', 'iqd', 'bhd', 'omr', 'qar'
]

# Time periods with their respective date calculations
time_periods = {
    '7_days': timedelta(days=7),
    '1_month': timedelta(days=30),
    '3_months': timedelta(days=90),
    '6_months': timedelta(days=180),
    '1_year': timedelta(days=365),
    '5_years': timedelta(days=1825),
    '10_years': timedelta(days=3650),
}

def deadend_format(date):
    return date.strftime('%Y-%m-%d')

def get_adjusted_now():
    return datetime.now() - timedelta(hours=3)

def get_start_date(period):
    adjusted_now = get_adjusted_now()
    return adjusted_now - time_periods[period]

def get_end_date():
    return get_adjusted_now()

def fetch_with_retry(url, data, retries=2, delay=5):
    for attempt in range(retries):
        response = requests.post(url, data=data)
        if response.status_code == 200:
            return response
        else:
            print(f"Attempt {attempt + 1} failed with status code {response.status_code}")
            time.sleep(delay)
    return None

def parse_html(html_content, currency_requested):
    soup = BeautifulSoup(html_content, 'html.parser')
    scripts = soup.find_all('script')

    for script in scripts:
        if 'data: {' in script.text:
            script_content = script.string

            # Check if the data corresponds to the requested currency
            currency_match = re.search(r"label:\s*'(\w+)'", script_content)
            if currency_match:
                currency_in_data = currency_match.group(1).upper()
                if currency_in_data != currency_requested.upper():
                    print(f"Data mismatch: requested {currency_requested}, got {currency_in_data}")
                    return None

            # Extract labels (dates) and data (prices)
            labels_match = re.search(r"labels:\s*\[(.*?)\]", script_content, re.DOTALL)
            data_match = re.search(r"data:\s*\[(.*?)\]", script_content, re.DOTALL)

            if labels_match and data_match:
                labels = labels_match.group(1)
                data_points = data_match.group(1)

                # Process labels
                date_strings = re.findall(r"new Date\('(\d{4}-\d{2}-\d{2})'\)", labels)
                dates = [datetime.strptime(date_str, '%Y-%m-%d') for date_str in date_strings]

                # Process data points
                prices = [int(price.strip()) for price in data_points.split(',')]

                if len(dates) != len(prices):
                    print("Error: data inconsistency")
                    return None

                # Combine dates and prices
                chart_data = [
                    {'date': deadend_format(date), 'price': price}
                    for date, price in zip(dates, prices)
                ]

                return chart_data
    return None

def fetch_data():
    url = 'https://gatsby.bl3ebird.workers.dev/graph'  # Replace with your actual URL

    # Ensure the 'results' directory exists
    results_dir = 'results'
    os.makedirs(results_dir, exist_ok=True)

    for currency in currencies:
        print(f"Processing currency: {currency}")

        # Create a subdirectory for each currency
        currency_dir = os.path.join(results_dir, currency)
        os.makedirs(currency_dir, exist_ok=True)

        for period in time_periods.keys():
            print(f"Processing {currency} for {period}")
            start_date = get_start_date(period)
            end_date = get_end_date()

            payload = {
                "currency": currency.lower(),  # Adjusted if API expects lowercase
                "stdate": deadend_format(start_date),
                "endate": deadend_format(end_date),
            }

            # Send POST request with retries
            response = fetch_with_retry(url, data=payload)
            if not response:
                print(f"Failed to fetch data for {currency} in {period} after retries")
                continue

            # Parse HTML and extract data
            data = parse_html(response.text, currency)
            if data:
                # Save data to JSON file inside the currency directory
                filename = f"{period}.json"
                filepath = os.path.join(currency_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=4)
                print(f"    Data saved to {filepath}")
            else:
                print(f"    No valid data for {currency} in {period}. Skipping.")
                # If parsing failed, do not overwrite existing data
                continue

            # Add a delay after each request
            print(f"    Waiting for 10 seconds before the next request...")
            time.sleep(10)  # Sleep for 10 seconds

if __name__ == '__main__':
    fetch_data()
