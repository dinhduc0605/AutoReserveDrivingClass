# AutoReserve

A Python script that automatically checks for available slots on the e-license website and sends notifications via Slack.

## Features

- Automatically logs into the e-license website
- Checks for available slots (elements with class 'status1')
- Navigates through multiple pages using the 'nextWeek' button
- Sends notifications to Slack with the available slots
- Runs every 20 seconds by default

## Script Functions

- `login_to_e_license(driver)`: Logs in to the e-license website using credentials from `.env`.
- `check_for_available_slots()`: Main logic to check for available slots, page through results, and trigger notifications if criteria are met.
- `find_status1_elements(driver)`: Extracts available slot data from the current page.
- `should_notify_for_slot(slot_data)`: Determines if a slot meets the notification criteria (e.g., within 2 weeks, weekends, evenings, or specific Wednesday time).
- `send_slack_notification(results)`: Sends a Slack message with all qualifying slots.
- `create_driver()`: Creates a headless Selenium WebDriver instance for Chrome/Chromium.
- `main()`: Runs the script in an infinite loop, checking for available slots every 20 seconds.


## Prerequisites

- Python 3.6 or higher
- Chrome or Chromium browser
- ChromeDriver (compatible with your Chrome/Chromium version)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd AutoReserve
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your credentials:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file and fill in your credentials:
   - `STUDENT_ID`: Your e-license student ID
   - `PASSWORD`: Your e-license password
   - `SLACK_TOKEN`: Your Slack API token (starts with `xoxb-`)
   - `SLACK_CHANNEL`: The Slack channel to send notifications to
   - Optional: `CHROMIUM_PATH` and `CHROMIUM_DRIVER_PATH` if using custom installations

## Usage

### Running the script

To run the script in normal mode (checking every 20 seconds):
```
python auto_reserve.py
```

To run the script once for testing:
```
python auto_reserve.py --test
```

### Setting up as a service

#### Using systemd (Linux)

Create a systemd service file:
```
sudo nano /etc/systemd/system/auto-reserve.service
```

Add the following content (adjust paths as needed):
```
[Unit]
Description=Auto Reserve Service
After=network.target

[Service]
User=<your-username>
WorkingDirectory=/path/to/AutoReserve
ExecStart=/usr/bin/python3 /path/to/AutoReserve/auto_reserve.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```
sudo systemctl enable auto-reserve.service
sudo systemctl start auto-reserve.service
```

#### Using cron (macOS/Linux)

Add a cron job to run the script:
```
crontab -e
```

# Note: The script is designed to run every 20 seconds in normal mode. Using cron for sub-minute intervals is not supported; use the script's built-in loop for frequent checks.


## Troubleshooting

### Common issues:

1. **Selenium errors**: Make sure you have the correct ChromeDriver version installed that matches your Chrome/Chromium version.

2. **Login failures**: Verify your credentials in the `.env` file.

3. **Slack notification errors**: Check your Slack token and channel name.

4. **Headless browser issues**: If you encounter issues with the headless browser, you can modify the `create_driver()` function in `auto_reserve.py` to remove the `--headless=new` option for debugging.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
