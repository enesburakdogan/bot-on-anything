# encoding:utf-8

import re

from bs4 import BeautifulSoup

from common import log
from housing_bot.listing import Listing
from housing_bot.sites.base import BaseSite

BASE_URL = "https://www.wg-gesucht.de"
# Berlin flats (category 2 = Wohnung), first result page
DEFAULT_SEARCH_URLS = [BASE_URL + "/wohnungen-in-Berlin.8.2.1.0.html"]

LOGIN_URL = BASE_URL + "/ajax/sessions.php?action=login"
CONVERSATION_URL = BASE_URL + "/ajax/conversations.php?action=conversations"


class WgGesuchtSite(BaseSite):
    key = "wg_gesucht"

    def __init__(self, conf):
        super().__init__(conf)
        if not self.search_urls:
            self.search_urls = DEFAULT_SEARCH_URLS
        self.email = conf.get("email", "")
        self.password = conf.get("password", "")
        self._logged_in = False

    # ---------- search ----------

    def search(self):
        listings = []
        for url in self.search_urls:
            try:
                resp = self.get(url)
                if resp.status_code != 200:
                    log.warn("[HousingBot][wg_gesucht] search page {} -> HTTP {}", url, resp.status_code)
                    continue
                listings.extend(self._parse_search_page(resp.text))
            except Exception as e:
                log.warn("[HousingBot][wg_gesucht] search failed for {}: {}", url, str(e))
        return listings

    def _parse_search_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for card in soup.select("div.wgg_card.offer_list_item"):
            listing = self._parse_card(card)
            if listing:
                results.append(listing)
        return results

    def _parse_card(self, card):
        ad_id = card.get("data-id", "")
        title_link = card.select_one("h2 a[href], h3 a[href]")
        if not ad_id or title_link is None:
            return None
        href = title_link.get("href", "")
        # skip partner/campaign ads that link off-site
        if not href.startswith("/"):
            return None

        listing = Listing(
            site=self.key,
            listing_id=ad_id,
            url=BASE_URL + href,
            title=title_link.get_text(strip=True),
        )

        # detail line: "2-Zimmer-Wohnung | Berlin Neukölln | Weserstraße"
        detail_span = card.select_one("div.col-xs-11 span")
        if detail_span:
            detail = re.sub(r"\s+", " ", detail_span.get_text(" ", strip=True))
            listing.address = detail
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*-\s*Zimmer", detail)
            if m:
                listing.rooms = float(m.group(1).replace(",", "."))
            parts = [p.strip() for p in detail.split("|")]
            if len(parts) >= 2:
                district = re.sub(r"^Berlin\s*", "", parts[1]).strip()
                listing.district = district

        card_text = card.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*€", card_text)
        if m:
            listing.price = int(m.group(1))
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", card_text)
        if m:
            listing.size = float(m.group(1).replace(",", "."))
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", card_text)
        if m:
            listing.available_from = m.group(1)
        return listing

    # ---------- apply ----------

    def login(self):
        if self._logged_in:
            return True
        if not self.email or not self.password:
            log.warn("[HousingBot][wg_gesucht] no credentials configured, cannot apply")
            return False
        payload = {
            "login_email_username": self.email,
            "login_password": self.password,
            "login_form_auto_login": "1",
            "display_language": "de",
        }
        resp = self.post(LOGIN_URL, json=payload, headers={"X-Requested-With": "XMLHttpRequest"})
        if resp.status_code != 200 or "detail" not in resp.text:
            log.warn("[HousingBot][wg_gesucht] login failed: HTTP {} {}", resp.status_code, resp.text[:200])
            return False
        if not self.session.cookies.get("X-Access-Token"):
            log.warn("[HousingBot][wg_gesucht] login did not yield access token; check credentials")
            return False
        self._logged_in = True
        log.info("[HousingBot][wg_gesucht] login OK")
        return True

    def apply(self, listing, message):
        """Send a message to the lister through WG-Gesucht's conversation API.

        Note: WG-Gesucht changes these internal endpoints from time to time;
        if applications start failing, compare with the requests the website
        makes when sending a message manually (browser dev tools).
        """
        if not self.login():
            return False, "login_failed"
        try:
            page = self.get(listing.url)
            csrf = self._extract(page.text, r'name="csrf_token"\s+value="([^"]+)"') or \
                self._extract(page.text, r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)')
            user_id = self._extract(page.text, r'data-user_id="(\d+)"') or \
                self._extract(page.text, r'"user_id"\s*:\s*"?(\d+)')
            if not user_id:
                return False, "no_user_id_on_page"

            headers = {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-Client-Id": "wg_desktop_website",
                "X-Authorization": "Bearer " + (self.session.cookies.get("X-Access-Token") or ""),
                "X-User-Id": self.session.cookies.get("X-User-Id") or "",
            }
            if csrf:
                headers["X-CSRF-Token"] = csrf
            payload = {
                "user_id": user_id,
                "ad_type": "0",
                "ad_id": listing.listing_id,
                "messages": [{"content": message, "message_type": "text"}],
            }
            resp = self.post(CONVERSATION_URL, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                log.info("[HousingBot][wg_gesucht] application sent for {}", listing.uid)
                return True, "sent"
            log.warn("[HousingBot][wg_gesucht] apply failed for {}: HTTP {} {}",
                     listing.uid, resp.status_code, resp.text[:300])
            return False, "http_{}".format(resp.status_code)
        except Exception as e:
            log.warn("[HousingBot][wg_gesucht] apply error for {}: {}", listing.uid, str(e))
            return False, "error"

    @staticmethod
    def _extract(text, pattern):
        m = re.search(pattern, text)
        return m.group(1) if m else None
