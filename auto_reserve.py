import os
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
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

def find_status1_elements(driver) -> List[Dict[str, Any]]:
    """
    Find all td elements with class 'status1' and extract structured datetime information.
    Returns a list of dictionaries, each containing parsed date/time components
    and a pre-formatted string.
    Example dict: {
        'year': 2025, 'month': 6, 'day': 27, 'hour': 9, 'minute': 0,
        'weekday_val': 4, # Monday is 0, Sunday is 6. From datetime.weekday()
        'formatted_str': '6月27日(金) 9:00'
    }
    """
    results = []
    try:
        # Find all td elements with class 'status1' but without class 'mikata-table'
        status1_elements = driver.find_elements(By.CSS_SELECTOR, "td.status1:not(.mikata-table)")
        
        for element in status1_elements:
            try:
                a_tag = element.find_element(By.TAG_NAME, "a")
                data_yoyaku = a_tag.get_attribute("data-yoyaku") # YYYYMMDD
                data_date = a_tag.get_attribute("data-date")     # M月D日 (e.g., 6月27日)
                data_time = a_tag.get_attribute("data-time")     # H:MM (e.g., 9:00)
                data_week = a_tag.get_attribute("data-week")     # (曜日) (e.g., (金))

                if data_yoyaku and data_time and data_date and data_week:
                    year = int(data_yoyaku[:4])
                    month = int(data_yoyaku[4:6])
                    day = int(data_yoyaku[6:])
                    hour, minute = map(int, data_time.split(':'))
                    
                    dt_obj = datetime(year, month, day, hour, minute)
                    weekday_val = dt_obj.weekday() # Monday is 0, Sunday is 6

                    # data_week includes parentheses like "(金)", so just concatenate
                    formatted_str = f"{data_date}{data_week} {data_time}"
                    
                    slot_data = {
                        'year': year, 'month': month, 'day': day, 
                        'hour': hour, 'minute': minute,
                        'weekday_val': weekday_val,
                        'formatted_str': formatted_str
                    }
                    results.append(slot_data)
            except Exception as e:
                print(f"Error extracting structured datetime from element: {e}")
        
        print(f"Found and processed {len(results)} status1 elements on current page.")
    except Exception as e:
        print(f"Error finding status1 elements: {e}")
    
    return results

def should_notify_for_slot(slot_data: Dict[str, Any]) -> bool:
    """
    Checks if a slot meets the notification criteria.
    - Must be within the next 2 weeks.
    - Weekends (Saturday or Sunday)
    - Weekdays and hour >= 19:00
    - Wednesday and hour = 13:00
    All datetime comparisons are based on Japan Standard Time (JST) implicitly,
    as the source data is from a Japanese website.
    """
    # Condition 0: Check if the slot is within the next 2 weeks.
    now = datetime.now()
    two_weeks_from_now = now + timedelta(weeks=2)
    slot_dt = datetime(
        slot_data['year'],
        slot_data['month'],
        slot_data['day'],
        slot_data['hour'],
        slot_data['minute']
    )
    if slot_dt > two_weeks_from_now:
        return False

    hour = slot_data['hour']
    weekday_val = slot_data['weekday_val'] # Monday is 0, Sunday is 6

    # Condition 1: Weekends
    if weekday_val == 5 or weekday_val == 6: # Saturday or Sunday
        return True
    
    # Condition 2: Weekdays and hour >= 19:00
    if 0 <= weekday_val <= 4 and hour >= 19: # Monday to Friday
        return True
        
    # Condition 3: Wednesday and hour = 13:00
    if weekday_val == 2 and hour == 13: # Wednesday
        return True
        
    return False

def check_for_available_slots():
    """
    Check for available slots on the e-license website.
    """
    all_slot_data_list = [] # Stores list of dicts from find_status1_elements
    
    with create_driver() as driver:
        if not login_to_e_license(driver):
            print("Failed to login. Aborting.")
            return
        
        has_next_page = True
        page_count = 1
        
        while has_next_page:
            print(f"Processing page {page_count}...")
            
            # Find all td elements with class 'status1' on current page
            page_slot_data_list = find_status1_elements(driver)
            all_slot_data_list.extend(page_slot_data_list)
            
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
    
    # Filter slots based on notification criteria
    slots_for_notification = [] # This will hold formatted strings of slots to notify
    if all_slot_data_list:
        for slot_data in all_slot_data_list:
            if should_notify_for_slot(slot_data):
                slots_for_notification.append(slot_data['formatted_str'])
        
        if slots_for_notification:
            send_slack_notification(slots_for_notification)
        else:
            print("No slots meeting notification criteria found.")
    else:
        print("No available slots found on any page.")

def send_slack_notification(results: List[str]):
    """
    Send a notification to Slack with the available slots.
    """
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        print("Slack token or channel not configured. Skipping notification.")
        return
    
    client = WebClient(token=SLACK_TOKEN)
    
    # 'results' here are the 'slots_for_notification' (formatted strings that met criteria)
    # Remove duplicates while preserving order from the already filtered list
    unique_filtered_results = []
    for result in results:
        if result not in unique_filtered_results:
            unique_filtered_results.append(result)

    if not unique_filtered_results:
        print("No unique slots to notify after filtering and duplicate removal. Skipping Slack notification.")
        return

    # Format the message
    message = "https://www.e-license.jp/el31/mSg1DWxRvAI-brGQYS-1OA==\n予約可能時間（フィルタ条件合致）：\n" # Updated title
    for result in unique_filtered_results:
        message += f"- {result}\n"
    
    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message
        )
        print(f"Slack notification sent for filtered slots at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
    
    # Schedule to run every 2 minutes
    schedule.every(2).minutes.do(check_for_available_slots)
    
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
