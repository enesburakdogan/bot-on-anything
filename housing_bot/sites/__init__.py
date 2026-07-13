# encoding:utf-8

from common import log


def create_sites(sites_conf):
    """Instantiate all enabled site adapters from the config block."""
    sites = []
    for key, conf in (sites_conf or {}).items():
        if not conf.get("enabled"):
            continue
        if key == "wg_gesucht":
            from housing_bot.sites.wg_gesucht import WgGesuchtSite
            sites.append(WgGesuchtSite(conf))
        elif key == "kleinanzeigen":
            from housing_bot.sites.kleinanzeigen import KleinanzeigenSite
            sites.append(KleinanzeigenSite(conf))
        else:
            log.warn("[HousingBot] unknown site '{}' in config, skipping", key)
    return sites
