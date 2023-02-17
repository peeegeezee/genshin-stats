import argparse
import asyncio
import logging
import os
import io
import pathlib
import time

import genshin
import jinja2
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument("-t", "--template", default="template.html", type=pathlib.Path)
parser.add_argument("-o", "--output", default="stats.html", type=pathlib.Path)
parser.add_argument("-c", "--cookies", default=None)
parser.add_argument("-l", "--lang", "--language", choices=genshin.LANGS, default="en-us")


async def main():
    args = parser.parse_args()
    cookies = args.cookies or os.environ["COOKIES"]

    client = genshin.Client(cookies, debug=True, game=genshin.Game.GENSHIN)

    user = await client.get_full_genshin_user(0, lang=args.lang)
    abyss = user.abyss.current if user.abyss.current.floors else user.abyss.previous
    diary = await client.get_diary()

    try:
        await client.claim_daily_reward(lang=args.lang, reward=False)
    except genshin.AlreadyClaimed:
        pass
    finally:
        reward = await client.claimed_rewards(lang=args.lang).next()
        reward_info = await client.get_reward_info()

    template = jinja2.Template(args.template.read_text())
    rendered = template.render(
        user=user,
        lang=args.lang,
        abyss=abyss,
        reward=reward,
        diary=diary,
        reward_info=reward_info,
    )
    args.output.write_text(rendered)
    
    #%% Get new codes

    res = requests.get("https://www.pockettactics.com/genshin-impact/codes")
    soup = BeautifulSoup(res.text, 'html.parser')

    active_codes = [code.text.strip() for code in soup.find("div", {"class":"entry-content"}).find("ul", recursive=False).findAll("strong")]

    codes_file = pathlib.Path(__file__).parent.resolve() / "codes.txt"
    used_codes = codes_file.open().read().split("\n")
    new_codes = list(filter(lambda x: x not in used_codes and x != "", active_codes))
    
    #%% Redeem new codes

    failed_codes = []
    for code in new_codes[:-1]:
        try:
            await client.redeem_code(code)
        except Exception as e:
            failed_codes.append(code)
        time.sleep(5.2)
    if len(new_codes) != 0:
        try:
            await client.redeem_code(new_codes[-1])
        except Exception as e:
            failed_codes.append(new_codes[-1])

    redeemed_codes = list(filter(lambda x: x not in failed_codes, new_codes))
    if len(redeemed_codes) != 0:
        print("Redeemed " + str(len(redeemed_codes)) + " new codes: " + ", ".join(redeemed_codes))
    else:
        print("No new codes found")


    #%% Add new codes to used codes

    used_codes.extend(new_codes)
    io.open(codes_file, "w", newline="\n").write("\n".join(used_codes))


if __name__ == "__main__":
    asyncio.run(main())
