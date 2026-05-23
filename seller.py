import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получает список товаров из магазина Ozon.

    Выполняет запрос к API Ozon для получения порции товаров с указанного last_id.

    Args:
        last_id: Идентификатор последнего товара из предыдущего запроса.
                Для первого запроса передаётся пустая строка.
        client_id: Идентификатор клиента Ozon.
        seller_token: API-ключ продавца Ozon.

    Returns:
        Словарь с результатом запроса, содержащий список товаров (ключ "items"),
        общее количество (ключ "total") и last_id для следующего запроса.
    
    Example:
        >>> result = get_product_list("", "12345", "token123")
        >>> result.get("items")

    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """Получает список всех артикулов (offer_id) товаров магазина Ozon.

    Выполняет пагинированный обход всех товаров с помощью get_product_list()
    и извлекает offer_id каждого товара.

    Args:
        client_id: Идентификатор клиента Ozon.
        seller_token: API-ключ продавца Ozon.

    Returns:
        Список строк с offer_id всех товаров в магазине.

    Example:
        >>> ids = get_offer_ids("12345", "token123")
        >>> len(ids)
        150

    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    """Обновляет цены товаров на Ozon.

    Отправляет список с ценами в API Ozon для массового обновления.

    Args:
        prices: Список словарей с ценами для обновления.
                Каждый словарь должен содержать поля: offer_id, price и др.
        client_id: Идентификатор клиента Ozon.
        seller_token: API-ключ продавца Ozon.

    Returns:
        Словарь с ответом API Ozon, содержащий результат операции.

    Raises:
        requests.exceptions.HTTPError: При ошибке HTTP-запроса (статус не 200).

    Example:
        >>> prices = [{"offer_id": "123", "price": "5990"}]
        >>> response = update_price(prices, "12345", "token123")

    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Обновляет остатки товаров на складе Ozon.

    Отправляет список с остатками в API Ozon для массового обновления.

    Args:
        stocks: Список словарей с остатками для обновления.
                Каждый словарь должен содержать поля: offer_id, stock.
        client_id: Идентификатор клиента Ozon.
        seller_token: API-ключ продавца Ozon.

    Returns:
        Словарь с ответом API Ozon, содержащий результат операции.

    Raises:
        requests.exceptions.HTTPError: При ошибке HTTP-запроса (статус не 200).

    Example:
        >>> stocks = [{"offer_id": "123", "stock": 10}]
        >>> response = update_stocks(stocks, "12345", "token123")

    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Скачивает и распаковывает файл с остатками товаров с сайта timeworld.ru.

    Загружает архив ostatki.zip, извлекает файл ostatki.xls,
    читает его в DataFrame, начиная с 17-й строки (пропуская шапку),
    и преобразует в список словарей. Временный файл удаляется после обработки.

    Returns:
        Список словарей с данными о товарах из Excel-файла.
        Ключи соответствуют названиям столбцов из файла.

    Raises:
        requests.exceptions.HTTPError: При ошибке загрузки файла.
        zipfile.BadZipFile: При повреждении архива.

    Example:
        >>> remnants = download_stock()
        >>> len(remnants)
        250

    """
    # Скачать остатки с сайта
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    # Создаем список остатков часов:
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")  # Удалить файл
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    """Формирует список остатков для загрузки на Ozon на основе внешних данных.

    Сопоставляет внешние остатки с offer_id из Ozon.
    Правила преобразования:
        - Количество ">10" → остаток 100
        - Количество "1" → остаток 0
        - Иное числовое значение → остаток без изменений
        - Товары из Ozon, отсутствующие во внешнем файле → остаток 0

    Args:
        watch_remnants: Список словарей с внешними данными (из download_stock).
                        Ожидаются ключи "Код" и "Количество".
        offer_ids: Список offer_id товаров из Ozon.

    Returns:
        Список словарей для API Ozon, каждый с ключами "offer_id" и "stock".

    Note:
        Функция изменяет исходный список offer_ids: удаляет из него offer_id,
        найденные во внешних данных.

    """
    # Уберем то, что не загружено в seller
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Формирует список цен для загрузки на Ozon на основе внешних данных.

    Создаёт ценовые предложения только для товаров, присутствующих в Ozon.

    Args:
        watch_remnants: Список словарей с внешними данными (из download_stock).
                        Ожидается ключ "Код" и "Цена".
        offer_ids: Список offer_id товаров из Ozon.

    Returns:
        Список словарей для API Ozon, каждый содержит:
            - auto_action_enabled: "UNKNOWN"
            - currency_code: "RUB"
            - offer_id: артикул товара
            - old_price: "0"
            - price: преобразованная цена через price_conversion()

    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """ Преобразует цену из формата внешнего файла в формат Ozon.

    Удаляет все символы, кроме цифр, и отбрасывает дробную часть (копейки).

    Args:
        price: Строка с ценой в формате внешнего источника.
               Пример: "5'990.00 руб."

    Returns:
        Строка, содержащая только цифры из целой части цены.
        Пример: "5990"

    Examples:
        Корректное исполнение:
        >>> price_conversion("5'990.00 руб.")
        '5990'
        >>> price_conversion("12 500.50")
        '12500'
        >>> price_conversion("3.200")
        '3200'
        >>> price_conversion("100")
        '100'

        Некорректное исполнение (текущая реализация не обрабатывает ошибки):
        >>> price_conversion("")          # пустая строка
        ''                                 # возвращает пустую строку
        >>> price_conversion("abc")       # нет цифр
        ''                                 # возвращает пустую строку
        >>> price_conversion(None)        # неверный тип
        AttributeError: 'NoneType' object has no attribute 'split'
    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разделяет список на части заданного размера.

    Генератор, который возвращает последовательные срезы списка по n элементов.

    Args:
        lst: Исходный список для разделения.
        n: Размер одной части (количество элементов).

    Yields:
        Список из n элементов (последний может быть короче).

    Example:
        >>> list(divide([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]

    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """Загружает цены товаров на Ozon.

    Получает список offer_id из магазина, формирует цены из внешних данных
    и отправляет их в API Ozon порциями по 1000 штук.

    Args:
        watch_remnants: Список словарей с внешними данными (из download_stock).
        client_id: Идентификатор клиента Ozon.
        seller_token: API-ключ продавца Ozon.

    Returns:
        Список сформированных цен (возвращаемое значение create_prices).

    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """Загружает остатки товаров на Ozon.

    Получает список offer_id из магазина, формирует остатки из внешних данных
    и отправляет их в API Ozon порциями по 100 штук.

    Args:
        watch_remnants: Список словарей с внешними данными (из download_stock).
        client_id: Идентификатор клиента Ozon.
        seller_token: API-ключ продавца Ozon.

    Returns:
        Кортеж (not_empty, stocks), где:
            - not_empty: список товаров с ненулевым остатком
            - stocks: полный список остатков (из create_stocks)

    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        # Обновить остатки
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        # Поменять цены
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
