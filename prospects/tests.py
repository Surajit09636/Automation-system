import os
import sys
from pathlib import Path

# 1. Add project root to sys.path so 'prospects' and 'config' can be imported
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 2. Initialize Django settings & apps
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.conf import settings
from django.core.mail import send_mail

# 3. Test Email Configuration
TEST_RECIPIENT = "surajitsutradhar010@gmail.com"
SUBJECT = "Test Email - Automation Outreach System"
MESSAGE = (
    "Hello,\n\n"
    "This is a test email sent from your Automation System via Brevo SMTP.\n"
    "Your email outreach integration is successfully connected and working!\n\n"
    "Best regards,\n"
    "Automation Outreach System"
)

def test_send_email():
    print("[Test] Starting Brevo SMTP Email Test")
    print(f"[Config] Backend:  {settings.EMAIL_BACKEND}")
    print(f"[Config] Host:     {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    print(f"[Config] TLS:      {settings.EMAIL_USE_TLS}")
    print(f"[Config] User:     {settings.EMAIL_HOST_USER}")
    print(f"[Config] From:     {settings.DEFAULT_FROM_EMAIL}")
    print(f"[Config] To:       {TEST_RECIPIENT}")

    try:
        print("[Sending] Connecting to Brevo SMTP and sending message...")
        sent = send_mail(
            subject=SUBJECT,
            message=MESSAGE,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[TEST_RECIPIENT],
            fail_silently=False,
        )
        
        print(f"[Success] Email sent successfully! ({sent} message sent)")
        print(f"[Success] Please check your inbox at: {TEST_RECIPIENT}")
        
    except Exception as e:
        
        print(f"[Error] Failed to send email: {e}")
        print("[Tip] Ensure 'clasynq@gmail.com' is added as a verified sender in your Brevo dashboard under Senders & IP.")

if __name__ == "__main__":
    test_send_email()
