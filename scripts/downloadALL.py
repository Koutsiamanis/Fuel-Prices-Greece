import os
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- Configuration ---
BASE_URL = "https://www.fuelprices.gr/"
TARGET_PAGE = "https://www.fuelprices.gr/deltia_dn.view"
DOWNLOAD_FOLDER = "./pdfs"

# Headers to mimic a real browser (prevents some 403 Forbidden errors)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def sanitize_filename(date_str):
    """Converts a date string like '04/12/2025' to a safe filename '2025-12-04.pdf'."""
    try:
        # Check if the date uses dots, slashes, or dashes
        parts = re.split(r'[/\.-]', date_str.strip())
        if len(parts) == 3:
            day, month, year = parts
            # Standardize to YYYY-MM-DD for sorting
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}.pdf"
    except Exception:
        pass
    # Fallback if parsing fails
    return f"{date_str.strip().replace('/', '_')}.pdf"

def download_pdfs():
    # 1. Create directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
        print(f"Created directory: {DOWNLOAD_FOLDER}")

    # 2. Fetch the main page listing all dates
    print(f"Fetching list from {TARGET_PAGE}...")
    try:
        response = requests.get(TARGET_PAGE, headers=HEADERS)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching main page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # 3. Find all links that look like dates (DD/MM/YYYY)
    # The regex looks for 1-2 digits, a separator, 1-2 digits, separator, 4 digits
    date_pattern = re.compile(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}')
    
    # We search for 'a' tags where the text matches the date pattern
    links = soup.find_all('a', string=date_pattern)

    print(f"Found {len(links)} documents to download.")

    # 4. Loop through links and download
    for index, link in enumerate(links):
        date_text = link.get_text(strip=True)
        relative_url = link.get('href')

        if not relative_url:
            continue

        # Construct full URL
        file_url = urljoin(BASE_URL, relative_url)
        filename = sanitize_filename(date_text)
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

        # Skip if already downloaded
        if os.path.exists(file_path):
            print(f"[{index+1}/{len(links)}] Skipping {filename} (already exists)")
            continue

        print(f"[{index+1}/{len(links)}] Downloading {filename}...")

        try:
            # Download the file content
            file_response = requests.get(file_url, headers=HEADERS, timeout=30)
            file_response.raise_for_status()

            # Write to disk
            with open(file_path, 'wb') as f:
                f.write(file_response.content)
            
            # Be polite to the server
            time.sleep(0.5) 

        except Exception as e:
            print(f"Failed to download {filename}: {e}")

    print("\nDownload process complete!")

if __name__ == "__main__":
    download_pdfs()