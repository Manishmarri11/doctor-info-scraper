import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from collections import deque
from urllib.robotparser import RobotFileParser
import time
import csv

MAX_PAGES = 50
REQUEST_DELAY = 1
SPECIALIZATION_KEYWORDS = [
    "dentist", "dermatologist", "cardiologist", "neurologist", "orthopedic",
    "surgeon", "pediatrician", "gynecologist", "psychiatrist", "urologist",
]
DOCTOR_NAME_PATTERN = re.compile(r"\bDr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")
QUALIFICATION_PATTERN = re.compile(r"\b(MBBS|MD|DO|DDS|PhD|MS|DMD)\b", re.I)
email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

def can_scrape(url):
    rp = RobotFileParser()
    rp.set_url(urljoin(url, "/robots.txt"))
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except:
        return True

def crawl_all_links(start_url, max_pages=MAX_PAGES):
    domain = urlparse(start_url).netloc
    queue = deque([start_url])
    visited = set()
    all_links = []

    while queue and len(all_links) < max_pages:
        url = queue.popleft()
        if url in visited or not can_scrape(url):
            continue

        visited.add(url)

        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Collect new links within same domain
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"])
                if urlparse(link).netloc == domain and link not in visited:
                    queue.append(link)

            all_links.append(url)
            time.sleep(REQUEST_DELAY)

        except requests.RequestException as e:
            print(f"Failed to access {url}: {e}")
            continue

    return all_links

# ------------------ Extract Doctor Info ------------------ #
def extract_doctor_info(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    doctors = []

    for match in DOCTOR_NAME_PATTERN.findall(text):

        qualifications = list(set(QUALIFICATION_PATTERN.findall(text)))

        specialization = [
            word for word in SPECIALIZATION_KEYWORDS
            if word.lower() in text.lower()
        ]

        emails = list(set(email_pattern.findall(text)))

        doctors.append({
            "name": match,
            "qualifications": qualifications,
            "specialization": specialization,
            "email": emails
        })

    return doctors

def write_to_csv(doctors, filename="doctors.csv"):
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # header
        writer.writerow(["Name", "Qualifications", "Specializations", "email"])

        # rows
        for doc in doctors:
            writer.writerow([
                doc["name"],
                ", ".join(doc["qualifications"]) or "N/A",
                ", ".join(doc["specialization"]) or "N/A",
                ", ".join(doc["email"]) or "N/A"
            ])

    print(f"✔ CSV file created: {filename}")

# ------------------ Main Scraper ------------------ #
def scrape_doctors_from_website(start_url):
    if not can_scrape(start_url):
        print(f"Scraping not allowed by robots.txt: {start_url}")
        return []

    pages = crawl_all_links(start_url)
    all_doctors = []

    for page in pages:
        try:
            resp = requests.get(page, timeout=5)
            resp.raise_for_status()
            doctors = extract_doctor_info(resp.text)
            if doctors:
                all_doctors.extend(doctors)
            time.sleep(REQUEST_DELAY)
        except requests.RequestException as e:
            print(f"Failed to scrape {page}: {e}")
            continue

    return all_doctors

# ------------------ Run ------------------ #
if __name__ == "__main__":
    site = input("Enter website URL: ")
    results = scrape_doctors_from_website(site)

    if results:
        write_to_csv(results)
    else:
        print("No doctor information found.")