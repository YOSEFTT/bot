import os
import imaplib
import email
import smtplib
import requests
from email.mime.text import MIMEText


# --- הגדרות קבועות ---
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# --- קבלת מיילים חדשים ---
def get_unread_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
        result, data = mail.search(None, '(UNSEEN)')
        if result != 'OK':
            print("[!] IMAP search failed")
            mail.logout()
            return []

        unread_msg_nums = data[0].split()
        messages = []

        for num in unread_msg_nums:
            # num הוא bytes; לא חובה להמיר אך אפשר
            result, msg_data = mail.fetch(num, "(RFC822)")
            if result != 'OK' or not msg_data or not msg_data[0]:
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            sender = email.utils.parseaddr(msg.get("From", ""))[1]
            subject = msg.get("Subject") if msg.get("Subject") else "(ללא נושא)"
            body = ""

            if msg.is_multipart():
                for part in msg.walk():
                    # נטפל גם ב־text/plain וגם ב־text/html במקרה שאין טקסט רגיל
                    content_type = part.get_content_type()
                    if content_type == "text/plain" and part.get_payload(decode=True):
                        charset = part.get_content_charset() or "utf-8"
                        body += part.get_payload(decode=True).decode(charset, errors="ignore")
                    elif content_type == "text/html" and not body and part.get_payload(decode=True):
                        # אם אין טקסט, נשמור את ה־ html כגיבוי
                        charset = part.get_content_charset() or "utf-8"
                        body += part.get_payload(decode=True).decode(charset, errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")

            messages.append({"from": sender, "subject": subject, "body": body})

        mail.logout()
        return messages
    except Exception as e:
        print(f"[!] Error fetching emails: {e}")
        return []


# --- שליחת מייל תשובה ---
def send_email(to_email, subject, body_text):
    try:
        formatted_text = body_text.replace('\n', '<br>')
        html_body = f"""
        <html>
        <body style="direction: rtl; text-align: right; font-family: Arial, sans-serif;">
        {formatted_text}
        </body>
        </html>
        """
        msg = MIMEText(html_body, _subtype='html', _charset='utf-8')
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = to_email
        msg['Subject'] = subject

        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, to_email, msg.as_string())

        print(f"[✔] Sent reply to {to_email}")
    except Exception as e:
        print(f"[!] Error sending email to {to_email}: {e}")


# --- קבלת תגובה מג'מיני ---
def get_gemini_reply(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            # נגן על מקרים שבהם המפתח לא נמצא
            try:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                return "תשובה לא נמצאה בתכנית התגובה של Gemini."
        else:
            print(f"[!] Gemini API error: {response.text}")
            return "אירעה שגיאה בעת יצירת התגובה."
    except Exception as e:
        print(f"[!] Error contacting Gemini API: {e}")
        return "שגיאה פנימית בתקשורת עם Gemini."


# --- הפעלת הבוט ---
def main():
    print("Starting Gemini Email Bot...")

    emails = get_unread_emails()
    if not emails:
        print("No new emails.")
        return

    for msg in emails:
        print(f"[📩] New email from: {msg['from']}")
        print(f"Subject: {msg['subject']}")
        body_preview = msg['body'][:200].replace('\n', ' ')
        print(f"Body (preview): {body_preview}...")
        reply = get_gemini_reply(msg["body"])
        send_email(msg["from"], f"Re: {msg['subject']}", reply)


if __name__ == "__main__":
    main()