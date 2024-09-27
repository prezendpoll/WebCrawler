import requests
from bs4 import BeautifulSoup
import itertools
import time
import nltk
import pandas as pd
from transformers import pipeline
import threading
import random
import json
import logging
import os
from collections import defaultdict

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Download the NLTK tokenizer
nltk.download('punkt')
summarizer = pipeline("summarization")

# User-Agent list for rotating requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL Build/QP1A.190711.020) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
]

# Configuration parameters
MAX_DEPTH = 3
MAX_RETRIES = 3
TIMEOUT = 5
SLEEP_TIME = 1
MAX_DOMAINS = 1000

# Function to generate domains with specified length and extensions
def generate_domains(length):
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    extensions = ['.com', '.org', '.net']
    for combo in itertools.product(chars, repeat=length):
        domain_name = ''.join(combo)
        for ext in extensions:
            yield f"{domain_name}{ext}"

# Function to fetch and extract information from a URL
def fetch_info(url):
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()  # Raise an error for bad status codes
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} - Failed to fetch {url}: {e}")
            time.sleep(SLEEP_TIME)  # Wait before retrying
    return None

# Function to extract title, description, and internal links from a page
def extract_info(domain, depth=0):
    if depth > MAX_DEPTH:
        return None
    
    page_content = fetch_info(f'http://{domain}')
    if page_content is None:
        return None

    soup = BeautifulSoup(page_content, 'html.parser')
    title = soup.title.string if soup.title else 'No Title'
    
    links_data = defaultdict(dict)
    for a in soup.find_all('a', href=True):
        link = a['href']
        if link.startswith('/') or domain in link:
            link_title = a.get_text(strip=True) or 'No Title'
            link_full = link if link.startswith('http') else f'http://{domain}{link}'
            links_data[link_full] = {
                'title': link_title,
                'description': 'Pending',
                'status': 'Pending'
            }
    
    # Generate a description based on the page's content
    text_content = ' '.join([p.get_text() for p in soup.find_all('p')])
    if len(text_content) > 0:
        try:
            description = summarizer(text_content, max_length=130, min_length=30, do_sample=False)[0]['summary_text']
        except Exception:
            description = 'Error summarizing content'
    else:
        description = 'No content to summarize'
    
    result = {
        'domain': domain,
        'title': title,
        'description': description,
        'links': links_data
    }
    
    # Fetch link descriptions and status codes
    for link in links_data.keys():
        link_info = extract_info(link, depth + 1)
        if link_info:
            links_data[link]['description'] = link_info['description']
            links_data[link]['status'] = 'Success'
        else:
            links_data[link]['status'] = 'Failed'

    return result

# Function to start the crawling process
def start_crawling():
    found_domains = []
    length = 1  # Start with 1-character domains
    while len(found_domains) < MAX_DOMAINS:
        for domain in generate_domains(length):
            logger.info(f"Processing domain: {domain}")
            info = extract_info(domain)
            if info:
                logger.info(f"Domain found: {domain}")
                found_domains.append(info)
                if len(found_domains) >= MAX_DOMAINS:
                    break
            else:
                logger.warning(f"Failed to access: {domain}")
            time.sleep(SLEEP_TIME)

        length += 1  # Increase the length for the next round of domain generation

    save_data(found_domains)

# Function to save data to CSV and JSON
def save_data(data):
    csv_filename = 'found_domains.csv'
    json_filename = 'found_domains.json'
    
    formatted_data = []
    for entry in data:
        domain_info = {
            'domain': entry['domain'],
            'title': entry['title'],
            'description': entry['description']
        }
        
        # Create a string for links information
        link_info_string = []
        for link, info in entry['links'].items():
            link_info_string.append(f"{link} | {info['title']} | {info['description']} | {info['status']}")
        
        link_info_str = '; '.join(link_info_string)
        formatted_data.append({**domain_info, 'links': link_info_str})

    # Save to CSV
    df = pd.DataFrame(formatted_data)
    df.to_csv(csv_filename, index=False)
    logger.info(f"Data saved to {csv_filename}")

    # Save to JSON
    with open(json_filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    logger.info(f"Data saved to {json_filename}")

# Function to run the crawler in a separate thread
def run_crawler():
    crawler_thread = threading.Thread(target=start_crawling)
    crawler_thread.start()
    crawler_thread.join()

# Function to provide a summary of the crawled data
def summarize_data(data):
    total_domains = len(data)
    total_links = sum(len(entry['links']) for entry in data)
    logger.info(f"Total domains crawled: {total_domains}")
    logger.info(f"Total internal links found: {total_links}")

# Function to handle configuration and run the crawler
def main():
    logger.info("Starting web crawler...")
    run_crawler()

# Start the crawler
if __name__ == '__main__':
    main()
