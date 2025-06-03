import os
import time
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import schedule
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# URL for e-license website
E_LICENSE_URL = "https://www.e-license.jp/el31/mSg1DWxRvAI-brGQYS-1OA=="

# Get credentials from environment variables
STUDENT_ID = os.getenv("STUDENT_ID")
PASSWORD = os.getenv("PASSWORD")
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")

def create_driver():
    """
    Create and return a headless Chromium WebDriver instance (or fallback to Chrome).
    """
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # Default paths for Ubuntu
    chromium_path = os.getenv('CHROMIUM_PATH')
    chromedriver_path = os.getenv('CHROMIUM_DRIVER_PATH')
    if chromium_path and os.path.exists(chromium_path):
        options.binary_location = chromium_path
    if chromedriver_path and os.path.exists(chromedriver_path):
        service = Service(executable_path=chromedriver_path)
        return webdriver.Chrome(service=service, options=options)
    # Fallback to default Chrome/driver
    return webdriver.Chrome(options=options)

def login_to_e_license(driver):
    """
    Login to the e-license website.
    """
    try:
        driver.get(E_LICENSE_URL)
        print("Navigated to e-license page.")

        wait = WebDriverWait(driver, 20)

        # Enter student ID
        student_id_input = wait.until(EC.presence_of_element_located((By.ID, "studentId")))
        student_id_input.send_keys(STUDENT_ID)

        # Enter password
        password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password_input.send_keys(PASSWORD)

        # Click login button
        login_button = wait.until(EC.element_to_be_clickable((By.ID, "login")))
        login_button.click()
        print("Logged in to e-license.")
        
        # Wait for page to load after login
        time.sleep(3)
        
        return True
    except Exception as e:
        print(f"Error during login: {e}")
        return False

def find_status1_elements(driver) -> List[str]:
    """
    Find all td elements with class 'status1' and extract the datetime information.
    Returns a list of formatted datetime strings like '6月27日(金) 9:00'.
    """
    results = []
    try:
        # Find all td elements with class 'status1' but without class 'mikata-table'
        status1_elements = driver.find_elements(By.CSS_SELECTOR, "td.status1:not(.mikata-table)")
        
        # Get datetime information from each element
        for element in status1_elements:
            try:
                # Find the <a> tag inside the td
                a_tag = element.find_element(By.TAG_NAME, "a")
                
                # Extract date and time attributes
                date_text = a_tag.get_attribute("data-date")
                time_text = a_tag.get_attribute("data-time")
                week_text = a_tag.get_attribute("data-week")
                
                # Format as '6月27日(金) 9:00'
                if date_text and time_text and week_text:
                    formatted_datetime = f"{date_text}{week_text} {time_text}"
                    results.append(formatted_datetime)
            except Exception as e:
                print(f"Error extracting datetime from element: {e}")
                # If we can't extract the attributes, fall back to text content
                content = element.text.strip()
                if content:
                    results.append(content)
        
        print(f"Found {len(results)} status1 elements on current page.")
    except Exception as e:
        print(f"Error finding status1 elements: {e}")
    
    return results

def check_for_available_slots():
    """
    Check for available slots on the e-license website.
    """
    all_results = []
    
    with create_driver() as driver:
        if not login_to_e_license(driver):
            print("Failed to login. Aborting.")
            return
        
        has_next_page = True
        page_count = 1
        
        while has_next_page:
            print(f"Processing page {page_count}...")
            
            # Find all td elements with class 'status1' on current page
            page_results = find_status1_elements(driver)
            all_results.extend(page_results)
            
            # Check if there's a next page button
            try:
                next_week_button = driver.find_element(By.CLASS_NAME, "nextWeek")
                next_week_button.click()
                print("Navigated to next week.")
                time.sleep(3)  # Wait for page to load
                page_count += 1
            except Exception as e:
                print("No more next week buttons found")
                has_next_page = False
    
    # Send results via Slack
    if all_results:
        send_slack_notification(all_results)
    else:
        print("No available slots found.")

def send_slack_notification(results: List[str]):
    """
    Send a notification to Slack with the available slots.
    """
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        print("Slack token or channel not configured. Skipping notification.")
        return
    
    client = WebClient(token=SLACK_TOKEN)
    
    # Remove duplicates while preserving order
    unique_results = []
    for result in results:
        if result not in unique_results:
            unique_results.append(result)
    
    # Format the message
    message = "https://www.e-license.jp/el31/mSg1DWxRvAI-brGQYS-1OA==\n*予約可能な時間：*\n"
    for result in unique_results:
        message += f"- {result}\n"
    
    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message
        )
        print(f"Slack notification sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except SlackApiError as e:
        print(f"Error sending Slack notification: {e.response['error']}")

def main():
    """
    Main function to schedule the checking of available slots.
    """
    print("Starting auto_reserve.py...")
    print(f"Will check for available slots every 3 minutes.")
    
    # Run once immediately
    check_for_available_slots()
    
    # Schedule to run every 3 minutes
    schedule.every(3).minutes.do(check_for_available_slots)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto Reserve script for e-license")
    parser.add_argument('--test', action='store_true', help='Run check immediately and exit')
    args = parser.parse_args()

    if args.test:
        check_for_available_slots()
    else:
        main()
