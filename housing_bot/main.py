# encoding:utf-8

"""HousingBot entry point.

Usage:
    python -m housing_bot.main --config housing_bot/config.json [--once]

Copy housing_bot/config-template.json to housing_bot/config.json first and
fill in your search criteria / credentials. If apply.ai.enabled is true, the
repo root config.json (bot-on-anything model config) must also be present.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import log  # noqa: E402
from housing_bot.runner import HousingBot  # noqa: E402


def load_housing_config(path):
    if not os.path.exists(path):
        raise Exception("Config not found: {} (copy housing_bot/config-template.json)".format(path))
    with open(path, mode="r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Berlin housing search & auto-apply bot")
    parser.add_argument("--config", type=str, default="./housing_bot/config.json",
                        help="path to housing bot config json")
    parser.add_argument("--once", action="store_true",
                        help="run a single crawl round and exit (no loop)")
    args = parser.parse_args()

    conf = load_housing_config(args.config)

    if conf.get("apply", {}).get("ai", {}).get("enabled"):
        # AI personalization uses the main bot-on-anything model config
        import config as app_config
        app_config.load_config(conf.get("model_config", "./config.json"))

    bot = HousingBot(conf)
    if args.once:
        bot.run_once(bootstrap=False)
    else:
        bot.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("[HousingBot] stopped by user")
