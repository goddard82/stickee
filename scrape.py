import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import re


# URL of the product page
url = "https://www.magpiehq.com/developer-challenge/smartphones/"

# Headers to mimic a generic browser request
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


def parse_capacity(capacity_text):
    """Extract capacity in MB from text like '64GB'."""
    try:
        return int(capacity_text.replace("GB", "").strip()) * 1024
    except ValueError:
        return None



def parse_shipping_date(shipping_text):
    """Extract and parse the shipping date from various shipping_text formats."""
    try:
        # If shipping_text includes "tomorrow" then return tomorrow's date
        if "tomorrow" in shipping_text.lower():
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # If shipping_text includes "Unavailable for delivery" then return None
        if "unavailable" in shipping_text.lower():
            return None

        # If shipping_text is in the format "Free Delivery Wednesday 15th Jan 2025" (remove weekday)
        # Remove 'Free Delivery' and weekday if present
        date_part = re.sub(r"^Free Delivery\s*", "", shipping_text)  # Remove "Free Delivery"
        date_part = re.sub(r"^[A-Za-z]+\s+", "", date_part)  # Remove weekday (e.g. "Wednesday")
        
        # If shipping date is in ISO format like "2025-01-15"
        try:
            parsed_date = datetime.strptime(date_part.strip(), "%Y-%m-%d")
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
        
        # If shipping_text is in a format like "Delivery from 13 Feb 2025"
        if "from" in shipping_text.lower():
            date_part = shipping_text.split("from")[-1].strip()

        # If shipping_text is in a format like "Delivery by 15 Jan 2025"
        if "by" in shipping_text.lower():
            date_part = shipping_text.split("by")[-1].strip()
        
        # If shipping_text is in a format like "Delivery by Wednesday 15th Jan 2025" (strip weekday)
        if "delivery by" in shipping_text.lower():
            date_part = shipping_text.split("by")[-1].strip()  # Remove "by" part
            date_part = re.sub(r'^[A-Za-z]+\s+', '', date_part)  # Remove weekday (e.g. "Wednesday")

        # Remove suffixes (st, nd, rd, th) and try to parse
        date_part = re.sub(r'\d+(st|nd|rd|th)', lambda x: x.group(0)[:-2], date_part)

        # Try parsing date format like "15 Jan 2025"
        try:
            parsed_date = datetime.strptime(date_part.strip(), "%d %b %Y")
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
        
        # If none of the cases matched, return None
        return None

    except Exception as e:
        print(f"Error parsing shipping date: {e}")
    return None



def scrape_products(base_url):
    page = 1
    all_products = []

    while True:
        # Fetch the HTML content of the page
        response = requests.get(f"{base_url}?page={page}", headers=headers)
        if response.status_code != 200:
            print(f"Failed to retrieve page {page}: {response.status_code}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all product elements
        products = soup.find_all('div', class_='product')  # Locate individual products
        if not products:
            print("No more products found.")
            break

        # Extract product details
        for product in products:
            try:
                # Product title
                product_name = product.find('span', class_='product-name').text.strip()
                product_capacity = product.find('span', class_='product-capacity').text.strip()
                title = f"{product_name} {product_capacity}"

                # Capacity in MB
                capacity_mb = parse_capacity(product_capacity)

                # Image URL
                image_tag = product.find('img')
                image_url = image_tag['src'].replace("../", "https://www.magpiehq.com/developer-challenge/smartphones/")  # Adjust relative path

                # Price
                price_text = product.find('div', class_='my-8 block text-center text-lg').text.strip()
                price = float(price_text.replace("£", "").strip())

                # Colours
                colour_elements = product.find_all('span', {'data-colour': True})
                colours = [el['data-colour'] for el in colour_elements]

                # Availability text
                availability_div = product.find('div', class_='my-4 text-sm block text-center', string=lambda s: "availability" in s.lower())
                availability_text = availability_div.get_text(strip=True) if availability_div else "Unavailable"

                # Shipping text
                shipping_div = product.find('div', class_='my-4 text-sm block text-center', string=lambda s: "delivery" in s.lower())
                shipping_text = shipping_div.get_text(strip=True) if shipping_div else "Unavailable for delivery"

                # Shipping date
                shipping_date = parse_shipping_date(shipping_text)

                # Check availability
                is_available = "in stock" in availability_text.lower()

                # Construct the product dictionary
                product_data = {
                    "title": title,
                    "price": price,
                    "imageUrl": image_url,
                    "capacityMB": capacity_mb,
                    "colour": colours,
                    "availabilityText": availability_text,
                    "isAvailable": is_available,
                    "shippingText": shipping_text,
                    "shippingDate": shipping_date,
                }
                all_products.append(product_data)
            except Exception as e:
                print(f"Error parsing product: {e}")

        # Go to the next page
        page += 1
        time.sleep(2)  # Delay between requests to avoid overloading the server

    # Save all products to a JSON file
    print("Scraping completed. Data saved to 'products.json'.")
    save_products_to_json(all_products)


def remove_duplicates(products):
    """Remove duplicate products based on title, keeping the one with more fields."""
    seen_titles = {}
    
    for product in products:
        # Ensure product is a dictionary (not a string)
        if isinstance(product, dict):
            title = product.get('title')
            if not title:
                continue  # Skip if there's no title (invalid product)

            # If this title has been seen before, compare the number of non-null fields
            if title in seen_titles:
                existing_product = seen_titles[title]
                
                # Count non-null fields for both products
                existing_non_null_fields = sum(1 for key, value in existing_product.items() if value is not None)
                current_non_null_fields = sum(1 for key, value in product.items() if value is not None)
                
                # Keep the product with more non-null fields
                if current_non_null_fields > existing_non_null_fields:
                    seen_titles[title] = product
            else:
                # If it's a new title, add it to the dictionary
                seen_titles[title] = product

        else:
            print(f"Skipping non-dictionary entry: {product}")  # Debugging log

    # Return the list of unique products
    return list(seen_titles.values())


# Save the final list to a JSON file
def save_products_to_json(products, filename='products.json'):
    """Save products to a JSON file, after removing duplicates."""
    # Ensure the input is a list of dictionaries
    if not isinstance(products, list):
        print("Error: Expected a list of products.")
        return
    
    unique_products = remove_duplicates(products)
    with open(filename, 'w') as f:
        json.dump(unique_products, f, indent=4)
    print(f"Products saved to '{filename}' after removing duplicates.")


# Start scraping process
scrape_products(url)
