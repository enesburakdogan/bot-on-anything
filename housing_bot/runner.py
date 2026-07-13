# encoding:utf-8

import random
import time

from common import log
from housing_bot.filters import ListingFilter
from housing_bot.message import MessageBuilder
from housing_bot.notifier import build_notifier
from housing_bot.sites import create_sites
from housing_bot.storage import Storage


class HousingBot:
    """Main loop: crawl sites -> filter -> dedupe -> (optionally) apply -> notify."""

    def __init__(self, conf):
        self.conf = conf
        self.filter = ListingFilter(conf.get("search", {}))
        self.sites = create_sites(conf.get("sites", {}))
        self.storage = Storage(conf.get("state_db", "./housing_state.db"))
        self.notifier = build_notifier(conf.get("notify", {}))

        apply_conf = conf.get("apply", {})
        self.apply_enabled = bool(apply_conf.get("enabled"))
        self.dry_run = bool(apply_conf.get("dry_run", True))
        self.max_per_hour = int(apply_conf.get("max_per_hour", 8))
        self.apply_delay = apply_conf.get("delay_seconds", [20, 90])
        self.message_builder = MessageBuilder(apply_conf)

        self.interval = int(conf.get("interval_seconds", 300))

        if not self.sites:
            raise RuntimeError("no site enabled in config (sites.*.enabled)")

    def run_forever(self):
        log.info("[HousingBot] starting: {} site(s), apply={}, dry_run={}, interval={}s",
                 len(self.sites), self.apply_enabled, self.dry_run, self.interval)
        self.notifier.send("🏠 HousingBot başladı ({} site, apply={}, dry_run={})".format(
            len(self.sites), self.apply_enabled, self.dry_run))
        first_round = True
        while True:
            try:
                self.run_once(bootstrap=first_round and bool(self.conf.get("skip_existing_on_first_run", True)))
            except Exception as e:
                log.error("[HousingBot] round failed")
                log.exception(e)
            first_round = False
            # jitter so the traffic pattern is not perfectly periodic
            sleep_for = self.interval + random.randint(0, max(1, self.interval // 5))
            log.info("[HousingBot] sleeping {}s", sleep_for)
            time.sleep(sleep_for)

    def run_once(self, bootstrap=False):
        """One crawl round. With bootstrap=True, existing listings are only
        recorded as seen (no application), so a freshly started bot does not
        mass-apply to the whole first result page at once."""
        for site in self.sites:
            listings = site.search()
            log.info("[HousingBot][{}] {} listing(s) on search pages", site.key, len(listings))
            fresh = 0
            for listing in listings:
                if self.storage.is_seen(listing.uid):
                    continue
                self.storage.mark_seen(listing)
                if bootstrap:
                    continue
                fresh += 1
                if not self.filter.accept(listing):
                    continue
                log.info("[HousingBot][{}] new match: {} ({})", site.key, listing.title, listing.url)
                self._handle_match(site, listing)
            if bootstrap:
                log.info("[HousingBot][{}] bootstrap round: existing listings recorded, none applied", site.key)
            else:
                log.info("[HousingBot][{}] {} new listing(s) this round", site.key, fresh)

    def _handle_match(self, site, listing):
        if not self.apply_enabled:
            self.notifier.send("🏠 Yeni ilan:\n" + listing.summary())
            return

        if self.storage.applications_since(3600) >= self.max_per_hour:
            log.warn("[HousingBot] hourly application limit ({}) reached, notifying only", self.max_per_hour)
            self.notifier.send("🏠 Yeni ilan (saatlik başvuru limiti doldu, başvuru GÖNDERİLMEDİ):\n"
                               + listing.summary())
            return

        message = self.message_builder.build(listing)
        if self.dry_run:
            self.storage.mark_applied(listing.uid, "dry_run")
            log.info("[HousingBot] DRY-RUN, would apply to {} with message:\n{}", listing.uid, message)
            self.notifier.send("🏠 Yeni ilan (DRY-RUN, başvuru gönderilmedi):\n{}\n\n--- Gönderilecek mesaj ---\n{}"
                               .format(listing.summary(), message))
            return

        # small human-like delay before contacting
        lo, hi = (self.apply_delay + [self.apply_delay[0]])[:2] if isinstance(self.apply_delay, list) else (20, 90)
        time.sleep(random.uniform(float(lo), float(hi)))

        ok, status = site.apply(listing, message)
        self.storage.mark_applied(listing.uid, "sent" if ok else "failed:" + status)
        if ok:
            self.notifier.send("✅ Başvuru gönderildi:\n" + listing.summary())
        else:
            self.notifier.send("⚠️ Başvuru BAŞARISIZ ({}):\n{}".format(status, listing.summary()))
