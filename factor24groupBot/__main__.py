import asyncio
import json
import logging
import sys
from pprint import pprint

import requests
import re
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import URLInputFile
from bs4 import BeautifulSoup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from factor24groupBot.settings import settings as envs


current_path = Path.cwd()
settings_path = Path(Path.joinpath(current_path, "settings.json"))


async def main() -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_script,
                      "cron",
                      hour="09-23/1",
                      max_instances=1)
    scheduler.start()


async def run_script() -> None:
    logging.info("Процесс получения объявлений запущен")

    text = get_notices_text()

    soup = BeautifulSoup(text, features="xml")
    offers = soup.find_all("offer")

    all_objects = get_offers_list(offers)
    logging.info(f"Парсинг завершен. Найдено {len(all_objects)} объектов")

    all_objects = sorted(all_objects, key=lambda obj: obj["internal_id"])
    max_id = all_objects[-1]["internal_id"]

    settings = get_settings_from_file(max_id)

    objects_to_show = list(filter(lambda obj: obj["internal_id"] > settings["LAST_ID"], all_objects))

    logging.info(f"Объекты отфильтрованы. К показу {len(objects_to_show)} объектов")

    if len(objects_to_show) > 0:
        bot = Bot(token=envs.bot_token, parse_mode=ParseMode.HTML)
        await bot.delete_webhook(drop_pending_updates=True)
        for notice in objects_to_show:
            logging.info(f"to show:{notice['internal_id']}")
            await bot.send_photo(
                chat_id=envs.target_chat_id,
                caption=get_caption(notice),
                photo=URLInputFile(notice['image']))
            await asyncio.sleep(1.5)
        await bot.session.close()

    save_settings_to_file(settings, max_id)


def get_notices_text() -> str:

    r = requests.get('http://x.faktor24.com/objects_1.xml')
    data = r.content
    text = data.decode("utf-8")

    data_file_path = Path(Path.joinpath(current_path,  "data.xml"))
    with open(data_file_path, 'wb') as fh:
        fh.write(data)

    # data_file_path = Path(Path.joinpath(current_path, "data.xml"))
    # with open(data_file_path, "r", encoding="utf-8") as fh:
    #     text = fh.read()

    return text


def get_settings_from_file(max_id: int) -> dict:
    if not settings_path.exists():
        settings = {
            "LAST_ID": max_id
        }
    else:
        with open(settings_path, "r", encoding='utf-8') as fh:
            settings = json.loads(fh.read())

    return settings


def save_settings_to_file(settings: dict, max_id: int) -> None:

    with open(settings_path, "w", encoding='utf-8') as fh:
        settings["LAST_ID"] = max_id
        fh.write(json.dumps(settings, indent=4))
        logging.info(f"ID последнего объекта {max_id} сохранен. Процесс завершен.")


def get_caption(notice: dict) -> str:
    commercial = ["дом", "участок", "коммерция"]

    if notice['category'].lower() in commercial:
        lot_area = "📏 <b>Площа ділянки:</b> " + notice['lot_area'] + "сот\n"
        rooms_count = ""
    else:
        lot_area = ""
        rooms_count = "🪟 #Кімнат_" + notice['rooms'] + "\n"

    if notice['category'].lower() == "дом":
        rooms_count = "🪟 #Кімнат_" + notice['rooms'] + "\n"

    caption = (f" #{notice['type']} #{notice['category']} ID{notice['internal_id']}\n"
               f"📍 #{notice['address']} #{notice['sub_locality_name']} #{notice['district']}\n"
               f"{rooms_count}"
               f"◽️ <b>Площа:</b> {notice['area']}м²\n"
               f"{lot_area}"
               f"💲 <b>Ціна:</b> {notice['price']}\n"
               f"📱 {notice['phone']} {notice['name']}\n"
               f"📩️️ <a href='https://t.me/faktor24com'>https://t.me/faktor24com</a>\n\n"
               f"Детальніше <a href='{notice['url']}'>на сайті тут</a>\n"
               f"Посилання на канал <a href='https://t.me/+arwgBDQGfg9mMTMy'>тут</a>\n"
               )

    return caption


def get_offers_list(offers: list) -> list:
    objects_to_show = []

    object_keys = ("internal_id", "url", "category", "type", "district", "address", "sub_locality_name",
                   "price", "image", "name", "phone", "area", "lot_area", "rooms")

    translations = {"продажа":"Продаж", "аренда":"Оренда", "квартира":"Квартири",
                    "дом":"Будинки", "коммерция":"Комерція", "участок":"Ділянки"}

    for offer in offers:
        try:
            notice = dict.fromkeys(object_keys)
            notice["internal_id"] = int(offer.get("internal-id"))
            notice["url"] = offer.find("url").text

            category = offer.find("category").text.lower()  # Продажа, Аренда
            notice["category"] = translations.get(category, category.capitalize())  # Квартира

            notice_type = offer.find("type").text.lower()  # Квартира, Дом, Коммерция...
            notice["type"] = translations.get(notice_type, notice_type.capitalize())

            notice["district"] = offer.find("district").text
            notice["sub_locality_name"] = offer.find("sub-locality-name").text.replace(" ", "_")
            address = offer.find("address").text  # <address>Болгарская, 37</address>
            notice["address"] = address.split(", ")[0].replace(" ", "_")

            rooms = offer.find("rooms")
            if rooms:
                notice["rooms"] = re.sub(r'[^0-9]', '', rooms.text)
            else:
                notice["rooms"] = "0"

            area = offer.find("area")
            if area:
                notice["area"] = re.sub(r'[^0-9]', '', area.text)
            else:
                notice["area"] = "0"

            lot_area = offer.find("lot-area")
            if lot_area:
                notice["lot_area"] = re.sub(r'[^0-9]', '', lot_area.text)
            else:
                notice["lot_area"] = "0"

            notice["price"] = offer.find("value").text

            name_array = offer.find("name").text.split(" ")  # <name>Юлия Александровна Курова</name>
            notice["name"] = f"{name_array[0]} {name_array[2]}"

            notice["phone"] = offer.find("phone").text

            image = offer.find("image")
            notice["image"] = image.text if image else None

            objects_to_show.append(notice)

        except Exception as e:
            logging.error(e)

    return objects_to_show


if __name__ == '__main__':
    logging.basicConfig(
        format='%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(stream=sys.stdout),
            logging.FileHandler(filename="app.log", mode="a")
        ],
        encoding="utf-8"
    )

    logging.info("Скрипт запущен")
    asyncio.run(run_script())

    # loop = asyncio.new_event_loop()
    # loop.create_task(main())
    # loop.run_forever()


