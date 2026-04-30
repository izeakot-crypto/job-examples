#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlareProx Helper для Indeed Parser

Предоставляет простой интерфейс для работы с FlareProx endpoints
"""

import json
import random
import logging
from pathlib import Path
from urllib.parse import quote

class FlareProxHelper:
    def __init__(self, endpoints_file="flareprox_endpoints.json"):
        """Инициализация FlareProx Helper"""
        self.endpoints_file = Path(endpoints_file)
        self.endpoints = self._load_endpoints()
        self.current_endpoint_index = 0

        if not self.endpoints:
            raise Exception(f"No FlareProx endpoints found in {endpoints_file}")

        logging.info(f"FlareProx initialized with {len(self.endpoints)} endpoints")

    def _load_endpoints(self):
        """Загрузка endpoints из JSON файла"""
        try:
            with open(self.endpoints_file, 'r', encoding='utf-8') as f:
                endpoints = json.load(f)
                return [ep['url'] for ep in endpoints if 'url' in ep]
        except Exception as e:
            logging.error(f"Failed to load FlareProx endpoints: {e}")
            return []

    def get_random_endpoint(self):
        """Получить случайный endpoint"""
        if not self.endpoints:
            return None
        return random.choice(self.endpoints)

    def get_next_endpoint(self):
        """Получить следующий endpoint (ротация по кругу)"""
        if not self.endpoints:
            return None

        endpoint = self.endpoints[self.current_endpoint_index]
        self.current_endpoint_index = (self.current_endpoint_index + 1) % len(self.endpoints)
        return endpoint

    def build_proxy_url(self, target_url, use_random=True):
        """
        Построить URL для проксирования через FlareProx

        Args:
            target_url: Целевой URL, который нужно загрузить через прокси
            use_random: Использовать случайный endpoint (True) или ротацию (False)

        Returns:
            Полный URL для запроса через FlareProx
        """
        endpoint = self.get_random_endpoint() if use_random else self.get_next_endpoint()
        if not endpoint:
            return target_url  # Fallback к прямому URL

        # FlareProx принимает target URL в query параметре
        proxy_url = f"{endpoint}?url={quote(target_url)}"
        return proxy_url

    def count_endpoints(self):
        """Получить количество доступных endpoints"""
        return len(self.endpoints)
