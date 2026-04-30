#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webshare Proxy Manager для Indeed Parser

Поддержка:
- Автоматическая загрузка прокси через API
- Умная ротация (случайная / последовательная)
- Health-check для проверки работоспособности
- Фильтрация по стране (опционально)
- Автоматическое обновление списка прокси
"""

import requests
import random
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json


class WebshareProxyManager:
    """
    Менеджер прокси от Webshare.io

    Пример использования:
        proxy_manager = WebshareProxyManager(api_key="your-api-key")
        proxy_config = proxy_manager.get_random_proxy()

        # С Camoufox
        with Camoufox(proxy=proxy_config, geoip=True) as browser:
            page = browser.new_page()
            page.goto('https://example.com')
    """

    def __init__(
        self,
        api_key: str,
        mode: str = "direct",  # "direct" или "backbone"
        country_codes: Optional[List[str]] = None,  # ["US", "ES", "FR"]
        cache_file: str = "webshare_proxies_cache.json",
        cache_hours: int = 24,  # Время жизни кеша
        check_health: bool = False,  # Проверять прокси перед использованием
        health_timeout: int = 10,  # Таймаут health-check
        preferred_protocol: str = "http"  # "http" или "socks5"
    ):
        """
        Инициализация менеджера прокси

        Args:
            api_key: API ключ от Webshare.io
            mode: Режим прокси - "direct" или "backbone"
            country_codes: Список кодов стран для фильтрации (например ["ES", "US"])
            cache_file: Файл для кеширования списка прокси
            cache_hours: Время жизни кеша в часах
            check_health: Проверять работоспособность прокси
            health_timeout: Таймаут для проверки работоспособности (секунды)
            preferred_protocol: Предпочитаемый протокол ("http" или "socks5")
        """
        self.api_key = api_key
        self.mode = mode
        self.country_codes = country_codes or []
        self.cache_file = Path(cache_file)
        self.cache_hours = cache_hours
        self.check_health = check_health
        self.health_timeout = health_timeout
        self.preferred_protocol = preferred_protocol

        self.proxies: List[Dict] = []
        self.current_index = 0
        self.failed_proxies: set = set()  # Список неработающих прокси

        logging.info(f"Webshare Proxy Manager initialized: mode={mode}, countries={country_codes}")

        # Загружаем прокси при инициализации
        self._load_proxies()

    def _load_proxies(self):
        """Загрузка прокси из кеша или через API"""
        # Проверяем кеш
        if self._load_from_cache():
            logging.info(f"Loaded {len(self.proxies)} proxies from cache")
            return

        # Загружаем через API
        logging.info("Cache not found or expired, fetching proxies from API...")
        self._fetch_proxies_from_api()

    def _load_from_cache(self) -> bool:
        """Загрузка прокси из кеша"""
        if not self.cache_file.exists():
            return False

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Проверяем время жизни кеша
            cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            if datetime.now() - cache_time > timedelta(hours=self.cache_hours):
                logging.info("Cache expired")
                return False

            self.proxies = cache_data.get('proxies', [])
            return len(self.proxies) > 0

        except Exception as e:
            logging.warning(f"Failed to load cache: {e}")
            return False

    def _save_to_cache(self):
        """Сохранение прокси в кеш"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'proxies': self.proxies
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Saved {len(self.proxies)} proxies to cache")
        except Exception as e:
            logging.warning(f"Failed to save cache: {e}")

    def _fetch_proxies_from_api(self):
        """Загрузка прокси через Webshare API"""
        url = "https://proxy.webshare.io/api/v2/proxy/list/"
        headers = {
            "Authorization": f"Token {self.api_key}"
        }

        params = {
            "mode": self.mode,
            "page": 1,
            "page_size": 100  # Максимум на страницу
        }

        # Фильтр по странам
        if self.country_codes:
            params["country_code__in"] = ",".join(self.country_codes)

        all_proxies = []

        try:
            while True:
                logging.info(f"Fetching page {params['page']}...")
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                results = data.get('results', [])
                all_proxies.extend(results)

                logging.info(f"  Page {params['page']}: {len(results)} proxies")

                # Проверяем пагинацию
                if not data.get('next'):
                    break

                params['page'] += 1
                time.sleep(0.5)  # Небольшая пауза между запросами

            self.proxies = all_proxies

            if len(self.proxies) == 0:
                logging.warning("No proxies found! Check your API key and subscription.")
            else:
                logging.info(f"Total proxies loaded: {len(self.proxies)}")
                self._save_to_cache()

        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch proxies from API: {e}")
            raise

    def _check_proxy_health(self, proxy: Dict) -> bool:
        """
        Проверка работоспособности прокси

        Args:
            proxy: Словарь с информацией о прокси

        Returns:
            True если прокси работает, False если нет
        """
        if not self.check_health:
            return True  # Пропускаем проверку если отключена

        proxy_url = self._format_proxy_url(proxy)
        test_urls = [
            "http://www.google.com",
            "https://api.ipify.org?format=text",
            "http://example.com"
        ]

        proxies_dict = {
            "http": proxy_url,
            "https": proxy_url
        }

        for test_url in test_urls:
            try:
                response = requests.get(
                    test_url,
                    proxies=proxies_dict,
                    timeout=self.health_timeout
                )
                if response.status_code == 200:
                    logging.debug(f"Proxy {proxy['proxy_address']} is healthy")
                    return True
            except Exception as e:
                logging.debug(f"Health check failed for {proxy['proxy_address']}: {e}")
                continue

        return False

    def _format_proxy_url(self, proxy: Dict, protocol: Optional[str] = None) -> str:
        """
        Форматирование конфигурации прокси для Camoufox

        Args:
            proxy: Словарь с информацией о прокси
            protocol: Протокол ("http" или "socks5"), если None - использует preferred_protocol

        Returns:
            URL прокси в формате: protocol://username:password@ip:port
        """
        proto = protocol or self.preferred_protocol

        # Для backbone (residential) прокси proxy_address = null, используем rotating endpoint
        if proxy['proxy_address'] is None:
            proxy_host = "p.webshare.io"
        else:
            proxy_host = proxy['proxy_address']

        return f"{proto}://{proxy['username']}:{proxy['password']}@{proxy_host}:{proxy['port']}"

    def _format_proxy_dict(self, proxy: Dict, protocol: Optional[str] = None) -> Dict:
        """
        Форматирование конфигурации прокси для Camoufox (словарь)

        Camoufox принимает прокси в формате:
        {
            'server': 'http://ip:port',
            'username': 'username',
            'password': 'password'
        }

        Args:
            proxy: Словарь с информацией о прокси
            protocol: Протокол ("http" или "socks5"), если None - использует preferred_protocol

        Returns:
            Словарь с конфигурацией прокси для Camoufox
        """
        proto = protocol or self.preferred_protocol

        # Для backbone (residential) прокси proxy_address = null, используем rotating endpoint
        if proxy['proxy_address'] is None:
            proxy_host = "p.webshare.io"
        else:
            proxy_host = proxy['proxy_address']

        return {
            'server': f"{proto}://{proxy_host}:{proxy['port']}",
            'username': proxy['username'],
            'password': proxy['password']
        }

    def get_random_proxy(self, as_dict: bool = True) -> Optional[Dict]:
        """
        Получить случайный прокси из списка

        Args:
            as_dict: Если True - возвращает словарь для Camoufox,
                     если False - возвращает строку URL

        Returns:
            Конфигурация прокси или None если все прокси неработоспособны
        """
        if not self.proxies:
            logging.error("No proxies available!")
            return None

        # Фильтруем рабочие прокси
        # Для residential прокси (backbone) используем ID вместо proxy_address
        available_proxies = [
            p for p in self.proxies
            if p.get('id') not in self.failed_proxies
        ]

        if not available_proxies:
            logging.warning("All proxies failed! Resetting failed list...")
            self.failed_proxies.clear()
            available_proxies = self.proxies

        proxy = random.choice(available_proxies)
        proxy_id = proxy.get('id') or proxy.get('proxy_address', 'unknown')
        logging.info(f"Selected random proxy: {proxy_id}:{proxy['port']} ({proxy['country_code']})")

        # Проверяем работоспособность
        if not self._check_proxy_health(proxy):
            proxy_id = proxy.get('id') or proxy.get('proxy_address', 'unknown')
            logging.warning(f"Proxy {proxy_id} failed health check")
            self.failed_proxies.add(proxy.get('id'))
            # Рекурсивно пытаемся получить другой прокси
            return self.get_random_proxy(as_dict=as_dict)

        if as_dict:
            return self._format_proxy_dict(proxy)
        else:
            return self._format_proxy_url(proxy)

    def get_next_proxy(self, as_dict: bool = True) -> Optional[Dict]:
        """
        Получить следующий прокси (последовательная ротация)

        Args:
            as_dict: Если True - возвращает словарь для Camoufox,
                     если False - возвращает строку URL

        Returns:
            Конфигурация прокси или None если все прокси неработоспособны
        """
        if not self.proxies:
            logging.error("No proxies available!")
            return None

        # Ищем следующий рабочий прокси
        attempts = 0
        max_attempts = len(self.proxies)

        while attempts < max_attempts:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)

            if proxy.get('id') not in self.failed_proxies:
                proxy_id = proxy.get('id') or proxy.get('proxy_address', 'unknown')
                logging.info(f"Selected next proxy: {proxy_id}:{proxy['port']} ({proxy['country_code']})")

                # Проверяем работоспособность
                if self._check_proxy_health(proxy):
                    if as_dict:
                        return self._format_proxy_dict(proxy)
                    else:
                        return self._format_proxy_url(proxy)
                else:
                    proxy_id = proxy.get('id') or proxy.get('proxy_address', 'unknown')
                    logging.warning(f"Proxy {proxy_id} failed health check")
                    self.failed_proxies.add(proxy.get('id'))

            attempts += 1

        logging.warning("All proxies failed! Resetting failed list...")
        self.failed_proxies.clear()
        return self.get_next_proxy(as_dict=as_dict)

    def mark_proxy_failed(self, proxy_config: Dict):
        """
        Пометить прокси как неработающий

        Args:
            proxy_config: Конфигурация прокси (словарь или строка URL)
        """
        if isinstance(proxy_config, dict):
            # Для residential прокси находим ID по username
            username = proxy_config.get('username', '')
            if username:
                # Ищем прокси с таким username
                for p in self.proxies:
                    if p.get('username') == username:
                        self.failed_proxies.add(p.get('id'))
                        logging.warning(f"Marked proxy as failed: {p.get('id')}")
                        return

            # Резервный вариант - извлекаем IP из server
            server = proxy_config.get('server', '')
            if '://' in server:
                ip = server.split('://')[1].split(':')[0]
                # Для residential это будет p.webshare.io, поэтому пытаемся найти по порту
                port_str = server.split(':')[-1]
                try:
                    port = int(port_str)
                    for p in self.proxies:
                        if p.get('port') == port:
                            self.failed_proxies.add(p.get('id'))
                            logging.warning(f"Marked proxy as failed: {p.get('id')}")
                            return
                except ValueError:
                    pass
        elif isinstance(proxy_config, str):
            # Извлекаем username из URL
            if '@' in proxy_config:
                username = proxy_config.split('://')[1].split(':')[0]
                for p in self.proxies:
                    if p.get('username') == username:
                        self.failed_proxies.add(p.get('id'))
                        logging.warning(f"Marked proxy as failed: {p.get('id')}")
                        return

    def get_proxy_count(self) -> int:
        """Получить общее количество прокси"""
        return len(self.proxies)

    def get_working_proxy_count(self) -> int:
        """Получить количество рабочих прокси"""
        return len(self.proxies) - len(self.failed_proxies)

    def refresh_proxies(self):
        """Принудительно обновить список прокси через API"""
        logging.info("Refreshing proxy list from API...")
        self.failed_proxies.clear()
        self._fetch_proxies_from_api()

    def get_proxies_info(self) -> List[Dict]:
        """
        Получить информацию о всех прокси

        Returns:
            Список словарей с информацией о прокси
        """
        return [
            {
                'ip': p['proxy_address'],
                'port': p['port'],
                'country': p['country_code'],
                'city': p.get('city_name', 'Unknown'),
                'valid': p['valid']
            }
            for p in self.proxies
        ]


# ================== УТИЛИТЫ ==================

def create_webshare_config_file(api_key: str, filename: str = "webshare_config.json"):
    """
    Создать конфигурационный файл для Webshare

    Args:
        api_key: API ключ от Webshare.io
        filename: Имя файла конфигурации
    """
    config = {
        "api_key": api_key,
        "mode": "direct",
        "country_codes": [],  # Пустой список = все страны
        "preferred_protocol": "http",
        "check_health": False,  # Отключаем для скорости
        "health_timeout": 10,
        "cache_hours": 24
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Конфигурационный файл создан: {filename}")
    print(f"⚠️  Не забудьте добавить {filename} в .gitignore!")


def load_webshare_config(filename: str = "webshare_config.json") -> Dict:
    """
    Загрузить конфигурацию из файла

    Args:
        filename: Имя файла конфигурации

    Returns:
        Словарь с настройками
    """
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


# ================== ТЕСТЫ ==================

if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Создаём тестовый конфиг
    print("=== Webshare Proxy Manager - Тест ===\n")

    # Загрузка конфига
    try:
        config = load_webshare_config()
        print(f"Загружен конфиг: {config}")
    except FileNotFoundError:
        print("Конфиг не найден, создаём тестовый...")
        api_key = input("Введите API ключ Webshare: ").strip()
        create_webshare_config_file(api_key)
        config = load_webshare_config()

    # Инициализация менеджера
    manager = WebshareProxyManager(
        api_key=config['api_key'],
        mode=config.get('mode', 'direct'),
        country_codes=config.get('country_codes', []),
        check_health=config.get('check_health', False),
        health_timeout=config.get('health_timeout', 10),
        preferred_protocol=config.get('preferred_protocol', 'http')
    )

    print(f"\n[+] Statistics:")
    print(f"  Total proxies: {manager.get_proxy_count()}")
    print(f"  Working proxies: {manager.get_working_proxy_count()}")

    # Получаем случайный прокси
    print(f"\n[+] Random proxy:")
    proxy = manager.get_random_proxy()
    print(f"  {json.dumps(proxy, indent=2)}")

    # Получаем следующий прокси
    print(f"\n[+] Next proxy:")
    proxy = manager.get_next_proxy()
    print(f"  {json.dumps(proxy, indent=2)}")

    # Информация о прокси
    print(f"\n[+] Proxy info (first 5):")
    proxies_info = manager.get_proxies_info()
    for info in proxies_info[:5]:  # Первые 5
        print(f"  {info['ip']}:{info['port']} - {info['country']} ({info['city']})")
