import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)


def get_product_list(page, campaign_id, access_token):
    """
    Получает список товаров с Яндекс Маркета.

    Что делает:
        Загружает страницу с товарами из вашего магазина на Яндекс Маркете.

    Что нужно передать:
        page (str): Номер страницы для загрузки (пустая строка = первая страница)
        campaign_id (str): ID вашей рекламной кампании в Яндекс Маркете
        access_token (str): Секретный ключ для доступа к Яндекс Маркету

    Что возвращает:
        dict: Словарь с данными о товарах (названия, цены, остатки)

    Когда может быть ошибка:
        Если неправильно указали access_token или campaign_id

    Пример правильного использования:
        >>> get_product_list("", "12345", "мой_секретный_ключ")
        {'offerMappingEntries': [...], 'paging': {...}}

    Пример с ошибкой:
        >>> get_product_list("", "неправильный_id", "ключ")
        Traceback (most recent call last):
        requests.exceptions.HTTPError: 404
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {
        "page_token": page,
        "limit": 200,
    }
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def update_stocks(stocks, campaign_id, access_token):
    """
    Обновляет информацию о количестве товаров на складе.

    Что делает:
        Отправляет на Яндекс Маркет новые данные о том, сколько товаров у вас есть в наличии.

    Что нужно передать:
        stocks (list): Список словарей с данными о товарах. 
                       Каждый словарь содержит: код товара, склад, количество.
        campaign_id (str): ID вашей рекламной кампании
        access_token (str): Секретный ключ для доступа к Яндекс Маркету

    Что возвращает:
        dict: Ответ от Яндекс Маркета (обычно {"status": "OK"})

    Когда может быть ошибка:
        Если не работает интернет или неправильный ключ доступа

    Пример правильного использования:
        >>> stocks = [{"sku": "123", "warehouseId": "1", "items": [{"count": 10}]}]
        >>> update_stocks(stocks, "12345", "мой_ключ")
        {'status': 'OK'}

    Пример с ошибкой:
        >>> update_stocks(stocks, "неправильный_id", "ключ")
        Traceback (most recent call last):
        requests.exceptions.HTTPError: 401
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def update_price(prices, campaign_id, access_token):
    """
    Обновляет цены на товары в Яндекс Маркете.

    Что делает:
        Отправляет новые цены на товары в ваш магазин на Яндекс Маркете.

    Что нужно передать:
        prices (list): Список словарей с новыми ценами. 
                       Каждый словарь содержит: код товара и новую цену.
        campaign_id (str): ID вашей рекламной кампании
        access_token (str): Секретный ключ для доступа к Яндекс Маркету

    Что возвращает:
        dict: Ответ от Яндекс Маркета (подтверждение обновления)

    Когда может быть ошибка:
        Если цена указана в неправильном формате

    Пример правильного использования:
        >>> prices = [{"id": "123", "price": {"value": 5000}}]
        >>> update_price(prices, "12345", "мой_ключ")
        {'status': 'OK'}

    Пример с ошибкой:
        >>> update_price(prices, "12345", "неправильный_ключ")
        Traceback (most recent call last):
        requests.exceptions.HTTPError: 403
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def get_offer_ids(campaign_id, market_token):
    """
    Получает список всех артикулов товаров из магазина на Яндекс Маркете.

    Что делает:
        Проходит по всем страницам вашего магазина и собирает коды (артикулы) всех товаров.

    Что нужно передать:
        campaign_id (str): ID вашей рекламной кампании
        market_token (str): Секретный ключ для доступа к Яндекс Маркету

    Что возвращает:
        list: Список строк с артикулами товаров, например: ['123', '456', '789']

    Пример правильного использования:
        >>> get_offer_ids("12345", "мой_ключ")
        ['Товар001', 'Товар002', 'Товар003']

    Пример с ошибкой:
        >>> get_offer_ids("неправильный_id", "ключ")
        Traceback (most recent call last):
        KeyError: 'offerMappingEntries'
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer").get("shopSku"))
    return offer_ids


def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """
    Создает список остатков товаров для отправки на Яндекс Маркет.

    Что делает:
        Превращает данные о часах из Excel-файла в формат, который понимает Яндекс Маркет.
        Если товара нет в списке - ставит остаток 0.
        Если указано ">10" - ставит 100 штук.
        Если указано "1" - ставит 0 (это значит "мало").

    Что нужно передать:
        watch_remnants (list): Список часов из Excel (содержит "Код" и "Количество")
        offer_ids (list): Список артикулов, которые уже есть на Маркете
        warehouse_id (str): Номер вашего склада на Яндекс Маркете

    Что возвращает:
        list: Список словарей с остатками в формате Яндекс Маркета

    Пример:
        >>> watch_remnants = [{"Код": "123", "Количество": "5"}]
        >>> offer_ids = ["123", "456"]
        >>> create_stocks(watch_remnants, offer_ids, "склад1")
        [
            {'sku': '123', 'warehouseId': 'склад1', 'items': [{'count': 5}]},
            {'sku': '456', 'warehouseId': 'склад1', 'items': [{'count': 0}]}
        ]
    """
    # Уберем то, что не загружено в market
    stocks = list()
    date = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append(
                {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
            )
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append(
            {
                "sku": offer_id,
                "warehouseId": warehouse_id,
                "items": [
                    {
                        "count": 0,
                        "type": "FIT",
                        "updatedAt": date,
                    }
                ],
            }
        )
    return stocks


def create_prices(watch_remnants, offer_ids):
    """
    Создает список цен для отправки на Яндекс Маркет.

    Что делает:
        Берет цены из Excel-файла и превращает их в формат для Яндекс Маркета.

    Что нужно передать:
        watch_remnants (list): Список часов из Excel (содержит "Код" и "Цена")
        offer_ids (list): Список артикулов, которые уже есть на Маркете

    Что возвращает:
        list: Список словарей с ценами в формате Яндекс Маркета

    Пример:
        >>> watch_remnants = [{"Код": "123", "Цена": "5000"}]
        >>> offer_ids = ["123"]
        >>> create_prices(watch_remnants, offer_ids)
        [{'id': '123', 'price': {'value': 5000, 'currencyId': 'RUR'}}]
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                # "feed": {"id": 0},
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    # "discountBase": 0,
                    "currencyId": "RUR",
                    # "vat": 0,
                },
                # "marketSku": 0,
                # "shopSku": "string",
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """
    Загружает цены на Яндекс Маркет.

    Что делает:
        1. Получает список всех товаров на Маркете
        2. Создает список цен для этих товаров
        3. Отправляет цены частями (по 500 штук)
        4. Ждет ответа от Маркета

    Что нужно передать:
        watch_remnants (list): Список часов с ценами
        campaign_id (str): ID кампании на Маркете
        market_token (str): Секретный ключ доступа

    Что возвращает:
        list: Список цен, которые были отправлены

    Пример:
        >>> цены = await upload_prices(часы, "12345", "мой_ключ")
        >>> print(f"Отправлено {len(цены)} цен")
        Отправлено 150 цен
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """
    Загружает остатки товаров на Яндекс Маркет.

    Что делает:
        1. Получает список всех товаров на Маркете
        2. Создает список остатков для этих товаров
        3. Отправляет остатки частями (по 2000 штук)
        4. Возвращает список товаров, которые есть в наличии

    Что нужно передать:
        watch_remnants (list): Список часов с остатками
        campaign_id (str): ID кампании на Маркете
        market_token (str): Секретный ключ доступа
        warehouse_id (str): Номер склада

    Что возвращает:
        tuple: (товары_в_наличии, все_остатки)
            - товары_в_наличии: список товаров, которых >0 штук
            - все_остатки: полный список всех остатков

    Пример:
        >>> в_наличии, все = await upload_stocks(часы, "12345", "ключ", "склад1")
        >>> print(f"Товаров в наличии: {len(в_наличии)}")
        Товаров в наличии: 42
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks


def main():
    """
    Главная функция программы.

    Что делает:
        1. Загружает настройки из переменных окружения (ключи, ID кампаний, склады)
        2. Скачивает данные о часах из Excel
        3. Обновляет остатки и цены для двух типов доставки (FBS и DBS)
        4. Ловит и показывает ошибки, если что-то пошло не так

    Как запустить:
        Просто выполните этот файл: python market.py

    Что нужно настроить перед запуском:
        Создайте файл .env с переменными:
            MARKET_TOKEN = ваш_секретный_ключ
            FBS_ID = ID_кампании_FBS
            DBS_ID = ID_кампании_DBS
            WAREHOUSE_FBS_ID = номер_склада_FBS
            WAREHOUSE_DBS_ID = номер_склада_DBS

    Пример ошибки, которую обрабатывает:
        - Нет интернета: "Ошибка соединения"
        - Долгий ответ: "Превышено время ожидания..."
        - Любая другая ошибка: покажет текст ошибки
    """
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        # FBS
        offer_ids = get_offer_ids(campaign_fbs_id, market_token)
        # Обновить остатки FBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_fbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_fbs_id, market_token)
        # Поменять цены FBS
        upload_prices(watch_remnants, campaign_fbs_id, market_token)

        # DBS
        offer_ids = get_offer_ids(campaign_dbs_id, market_token)
        # Обновить остатки DBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_dbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_dbs_id, market_token)
        # Поменять цены DBS
        upload_prices(watch_remnants, campaign_dbs_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
