import requests
import os

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        """
        Initializes the Telegram Notifier.

        Args:
            bot_token (str, optional): The Telegram Bot Token. Defaults to env var TELEGRAM_BOT_TOKEN.
            chat_id (str, optional): The Telegram Chat ID to send messages to. Defaults to env var TELEGRAM_CHAT_ID.
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        if not self.bot_token:
            print("TelegramNotifier Warning: Bot Token is missing. Notifications will fail.")
        if not self.chat_id:
            print("TelegramNotifier Warning: Chat ID is missing. Notifications will fail.")

    def is_configured(self):
        """Checks if both bot_token and chat_id are configured."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, message_text, parse_mode="Markdown"):
        """
        Sends a message to the configured Telegram chat.

        Args:
            message_text (str): The text of the message to send.
            parse_mode (str, optional): Formatting mode for the message ('Markdown', 'HTML').
                                       Defaults to "Markdown". Use "MarkdownV2" for more complex markdown.

        Returns:
            bool: True if the message was sent successfully (HTTP 200), False otherwise.
            dict: The JSON response from Telegram API, or an error dictionary.
        """
        if not self.is_configured():
            error_msg = "Telegram Notifier is not configured (missing Bot Token or Chat ID)."
            print(f"TelegramNotifier Error: {error_msg}")
            return False, {"ok": False, "description": error_msg}

        payload = {
            'chat_id': self.chat_id,
            'text': message_text,
            'parse_mode': parse_mode
        }

        try:
            response = requests.post(self.base_url, data=payload, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

            response_json = response.json()
            if response_json.get("ok"):
                print(f"TelegramNotifier: Message sent successfully to chat_id {self.chat_id[:4]}... .")
                return True, response_json
            else:
                desc = response_json.get('description', 'Unknown error from Telegram API.')
                print(f"TelegramNotifier Error: Failed to send message. Telegram API Error: {desc}")
                return False, response_json

        except requests.exceptions.RequestException as e:
            print(f"TelegramNotifier Error: Request failed - {e}")
            return False, {"ok": False, "description": f"RequestException: {e}"}
        except Exception as e:
            print(f"TelegramNotifier Error: An unexpected error occurred - {e}")
            return False, {"ok": False, "description": f"Unexpected error: {e}"}

    def update_credentials(self, bot_token, chat_id):
        """Updates the bot token and chat ID."""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        print("TelegramNotifier: Credentials updated.")
        if not self.is_configured():
             print("TelegramNotifier Warning: Updated credentials still incomplete.")


if __name__ == '__main__':
    print("--- Testing TelegramNotifier ---")
    # To test this, set environment variables:
    # TELEGRAM_BOT_TOKEN="your_actual_bot_token"
    # TELEGRAM_CHAT_ID="your_actual_chat_id"
    # Or pass them directly to the constructor.

    # Test Case 1: Using environment variables (if set)
    print("\nTest Case 1: Initialize with environment variables (if set)")
    notifier_env = TelegramNotifier()
    if notifier_env.is_configured():
        print(f"Notifier configured with Token: ...{notifier_env.bot_token[-6:]}, Chat ID: {notifier_env.chat_id}")
        success, resp = notifier_env.send_message("Hello from *TelegramNotifier* (Test 1 - Env Vars)! This is a test message.\nVisit [Google](https://google.com).")
        print(f"Send Message Success: {success}, Response: {resp.get('description', 'N/A') if not success else 'OK'}")
    else:
        print("Skipping Test Case 1: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables not set.")

    # Test Case 2: Passing credentials directly
    print("\nTest Case 2: Initialize with direct credentials (replace with your actual test credentials if desired)")
    # IMPORTANT: Replace with dummy or your actual test token/chat_id for this test to run.
    # Do not commit real sensitive tokens to version control.
    test_bot_token = os.getenv('TELEGRAM_BOT_TOKEN_TEST', "YOUR_DUMMY_OR_TEST_BOT_TOKEN")
    test_chat_id = os.getenv('TELEGRAM_CHAT_ID_TEST', "YOUR_DUMMY_OR_TEST_CHAT_ID")

    if test_bot_token != "YOUR_DUMMY_OR_TEST_BOT_TOKEN" and test_chat_id != "YOUR_DUMMY_OR_TEST_CHAT_ID":
        notifier_direct = TelegramNotifier(bot_token=test_bot_token, chat_id=test_chat_id)
        if notifier_direct.is_configured():
            print(f"Notifier configured with Token: ...{notifier_direct.bot_token[-6:]}, Chat ID: {notifier_direct.chat_id}")
            success_direct, resp_direct = notifier_direct.send_message(
                "Hello from *TelegramNotifier* (Test 2 - Direct Credentials)! \n"
                "```python\nprint('Code block')\n```"
                "Visit [OpenAI](https://openai.com).",
                parse_mode="Markdown" # Or MarkdownV2, but ensure content is escaped properly for V2
            )
            print(f"Send Message Success (Direct): {success_direct}, Response: {resp_direct.get('description', 'N/A') if not success_direct else 'OK'}")
        else:
            print("Test Case 2: Notifier still not configured with direct credentials (likely dummy values).")
    else:
        print("Skipping Test Case 2: Dummy token/chat_id found. Replace with real test values or set _TEST env vars to run.")

    # Test Case 3: Not configured
    print("\nTest Case 3: Not configured")
    notifier_unconfigured = TelegramNotifier(bot_token=None, chat_id=None) # Force unconfigured
    if not notifier_unconfigured.is_configured():
        print("Notifier is correctly detected as not configured.")
        success_unconf, resp_unconf = notifier_unconfigured.send_message("This message should not send.")
        print(f"Send Message Success (Unconfigured): {success_unconf}, Response Description: {resp_unconf.get('description')}")
        assert not success_unconf
    else:
        print("Test Case 3 Error: Notifier unexpectedly configured.")

    # Test Case 4: Update credentials
    print("\nTest Case 4: Update credentials")
    notifier_update = TelegramNotifier(bot_token="old_token", chat_id="old_chat_id")
    print(f"Initial config: Token ending ...{notifier_update.bot_token[-6:]}, Chat ID: {notifier_update.chat_id}")
    if test_bot_token != "YOUR_DUMMY_OR_TEST_BOT_TOKEN" and test_chat_id != "YOUR_DUMMY_OR_TEST_CHAT_ID":
        notifier_update.update_credentials(bot_token=test_bot_token, chat_id=test_chat_id)
        print(f"Updated config: Token ending ...{notifier_update.bot_token[-6:]}, Chat ID: {notifier_update.chat_id}")
        if notifier_update.is_configured():
            success_upd, resp_upd = notifier_update.send_message("Test after credentials update.")
            print(f"Send Message Success (Updated): {success_upd}, Response: {resp_upd.get('description', 'N/A') if not success_upd else 'OK'}")
    else:
        print("Skipping Test Case 4 send message part: Dummy token/chat_id for update.")

    print("\nTelegramNotifier tests completed. Check your Telegram for messages if tests were run with valid credentials.")
