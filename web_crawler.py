import requests
from bs4 import BeautifulSoup
import itertools
import time
import nltk
import pandas as pd
from transformers import pipeline

# Initialize the NLP summarization model
nltk.download('punkt')
summarizer = pipeline("summarization")

# Function to generate domains with specified length and extensions
def generate_domains(length):
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    extensions = ['.com', '.org', '.net']
    # Generate all combinations of given length
    for combo in itertools.product(chars, repeat=length):
        domain_name = ''.join(combo)
        for ext in extensions:
            yield f"{domain_name}{ext}"

# Function to extract title, description, and internal links from a page
def extract_info(domain):
    try:
        response = requests.get(f'http://{domain}', timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else 'No Title'
            
            # Extract all internal links and their titles/descriptions
            links_data = {}
            for a in soup.find_all('a', href=True):
                link = a['href']
                if link.startswith('/') or domain in link:
                    link_title = a.get_text(strip=True) or 'No Title'
                    link_full = link if link.startswith('http') else f'http://{domain}{link}'
                    
                    # Fetching the description for the internal link
                    link_info = extract_info(link_full)  # This will recurse into the link
                    if link_info:  # Ensure we got valid info
                        link_description = link_info['description']
                    else:
                        link_description = 'Failed to access link'
                    
                    # Store the link with its title and description
                    links_data[link_full] = {
                        'title': link_title,
                        'description': link_description
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
            
            return {
                'domain': domain,
                'title': title,
                'description': description,
                'links': links_data
            }
        else:
            return None
    except requests.exceptions.RequestException:
        return None

# Main crawling function
def start_crawling():
    found_domains = []
    length = 1  # Start with 1-character domains
    while len(found_domains) < 1000:  # Collect up to 1000 valid entries
        for domain in generate_domains(length):
            info = extract_info(domain)
            if info:
                print(f"Domain found: {domain}")
                found_domains.append(info)
                # Save data after every successful extraction
                save_data(found_domains)
                # Stop if we have collected 1000 entries
                if len(found_domains) >= 1000:
                    break
            else:
                print(f"Failed to access: {domain}")
            time.sleep(1)  # Pause 1 second between requests to avoid overloading servers
        
        length += 1  # Increase the length for the next round of domain generation

# Function to save data to CSV
def save_data(data):
    formatted_data = []
    for entry in data:
        domain_info = {
            'domain': entry['domain'],
            'title': entry['title'],
            'description': entry['description']
        }

        # Add all links information
        for link, info in entry['links'].items():
            link_info = {
                'link': link,
                'link_title': info['title'],
                'link_description': info['description']
            }
            formatted_data.append({**domain_info, **link_info})

    df = pd.DataFrame(formatted_data)
    df.to_csv('found_domains.csv', index=False)

# Start the crawler
start_crawling()
