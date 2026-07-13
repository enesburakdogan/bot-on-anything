# encoding:utf-8

import requests

from common import log


class TelegramNotifier:
    """Sends plain-text notifications about new listings / applications
    to a Telegram chat via the Bot API."""

    def __init__(self, conf):
        self.enabled = bool(conf.get("enabled"))
        self.bot_token = conf.get("bot_token", "")
        self.chat_id = conf.get("chat_id", "")
        if self.enabled and (not self.bot_token or not self.chat_id):
            log.warn("[HousingBot] telegram notifier enabled but bot_token/chat_id missing, disabling")
            self.enabled = False

    def send(self, text):
        if not self.enabled:
            return
        try:
            resp = requests.post(
                "https://api.telegram.org/bot{}/sendMessage".format(self.bot_token),
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                timeout=15,
            )
            if resp.status_code != 200:
                log.warn("[HousingBot] telegram notify failed: {} {}", resp.status_code, resp.text[:200])
        except Exception as e:
            log.warn("[HousingBot] telegram notify error: {}", str(e))


def build_notifier(notify_conf):
    telegram_conf = (notify_conf or {}).get("telegram", {})
    return TelegramNotifier(telegram_conf)
