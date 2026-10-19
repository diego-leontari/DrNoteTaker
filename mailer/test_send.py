import sys

from mailer.send import send_email

HTML = (
    "<h2>Doctor Note Taker test</h2>"
    "<p>This is a test email sent through <b>Composio</b> (Gmail).</p>"
    "<p>Fictional demo data only.</p>"
)


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m mailer.test_send you@gmail.com")
        sys.exit(1)
    to = sys.argv[1]
    result = send_email(to, "Doctor Note Taker test", HTML)
    print(result)
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
