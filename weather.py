import time
import requests
import smtplib
from imapclient import IMAPClient
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading

# Email configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
IMAP_SERVER = 'imap.gmail.com'
IMAP_PORT = 993
SENDER_EMAIL = 'YOUREMAIL@gmail.com'
SENDER_PASSWORD = 'APP_PASSWORD'
GOOGLE_GEOCODING_API_KEY = 'API_KEY'

# Optimization parameters
CHECK_INTERVAL = 30  # Sleep interval between email checks (in seconds)

def get_weather(lat, lon):
    forecast_url = 'https://forecast.weather.gov/MapClick.php?lat={}&lon={}&FcstType=json&TextType=2'.format(lat, lon)

    response = requests.get(forecast_url)

    if response.status_code == 200:
        data = response.json()

        area_description = data['location']['areaDescription']
        periods = data['time']['startPeriodName']
        temperatures = data['data']['temperature']
        weather_conditions = data['data']['weather'] #Brief Forecast       
#       weather_conditions = data['data']['text'] #Extended Forecast

        weather_info = []
        for period, temperature, weather in zip(periods, temperatures, weather_conditions):
            weather_info.append("{}: {}°F, {}".format(period, temperature, weather))

        return area_description, "\n".join(weather_info)

    return None, None

def send_email(subject, body, recipient_email):
    message = MIMEMultipart()
    message['From'] = SENDER_EMAIL
    message['To'] = recipient_email
    message['Subject'] = subject

    email_body = "{}\n\nWinlink Weather Forecast by NA7Q (2023)".format(body)  # Add the signature to the email body
    message.attach(MIMEText(email_body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, message.as_string())
        server.quit()
        print('Email sent successfully!')
    except smtplib.SMTPException as e:
        print('Email could not be sent:', e)

def check_emails():
    try:
        with IMAPClient(IMAP_SERVER, port=IMAP_PORT) as client:
            client.login(SENDER_EMAIL, SENDER_PASSWORD)
            client.select_folder('INBOX')
            messages = client.search(['UNSEEN'])
            if messages:
                print('Received', len(messages), 'new email(s)')

            for msgid, message_data in client.fetch(messages, ['RFC822']).items():
                raw_email = message_data[b'RFC822']
                email_message = email.message_from_bytes(raw_email)

                sender = email_message['From']
                subject = email_message['Subject']

                # Check if the email subject contains location information
                try:
                    subject = subject.decode()
                except AttributeError:
                    pass

                if subject.lower().startswith('location'):
                    location = subject[9:].strip()
                    print('Received email with location:', location)

                    # Use Google Geocoding API to get latitude and longitude
                    geocode_url = 'https://maps.googleapis.com/maps/api/geocode/json?address={}&key={}'.format(location, GOOGLE_GEOCODING_API_KEY)

                    geocode_response = requests.get(geocode_url)
                    if geocode_response.status_code == 200:
                        geocode_data = geocode_response.json()
                        if geocode_data['status'] == 'ZERO_RESULTS':
                            send_email('Weather Forecast', 'No weather information found for the provided location.', sender)
                            print('No weather information found for location:', location)
                            continue

                        lat = geocode_data['results'][0]['geometry']['location']['lat']
                        lon = geocode_data['results'][0]['geometry']['location']['lng']

                        area_description, weather_info = get_weather(lat, lon)

                        if area_description and weather_info:
                            email_body = "{}\n\n{}".format(area_description, weather_info)
                            send_email('Weather Forecast', email_body, sender)
                            print('Weather forecast sent to:', sender)
                        else:
                            send_email('Weather Forecast', 'Unable to retrieve weather information for the provided location.', sender)
                            print('Failed to retrieve weather information for location:', location)
                    else:
                        print('Failed to retrieve geocoding data for the provided location.')

                # Mark the email as read
                client.set_flags(msgid, [b'\\Seen'])

    except Exception as e:
        print('An error occurred:', e)

def listen_emails():
    while True:
        check_emails()
        time.sleep(CHECK_INTERVAL)

def start_email_listener():
    email_thread = threading.Thread(target=listen_emails)
    email_thread.daemon = True
    email_thread.start()

    print('Email listener started.')

start_email_listener()

# Keep the main thread running to continue the script execution
while True:
    time.sleep(1)
