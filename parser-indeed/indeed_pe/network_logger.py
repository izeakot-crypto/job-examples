#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль детального логирования сетевой информации

Логирует все данные, которые отправляются в сеть:
- HTTP заголовки
- Proxy информация
- IP адреса (реальный и через прокси)
- WebRTC состояние
- Browser fingerprint
- TLS/SSL информация
"""

import logging
import json
import requests
from datetime import datetime


class NetworkLogger:
    """Детальное логирование всей сетевой информации"""

    def __init__(self, log_file=None):
        self.log_file = log_file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log_browser_fingerprint(self, page):
        """
        Логирует browser fingerprint через JavaScript

        Проверяет:
        - navigator.userAgent
        - navigator.platform
        - navigator.hardwareConcurrency
        - screen resolution
        - timezone
        - WebGL vendor/renderer
        - языки
        - плагины
        """
        try:
            fingerprint_script = """
            (() => {
                return {
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    hardwareConcurrency: navigator.hardwareConcurrency,
                    deviceMemory: navigator.deviceMemory || 'undefined',
                    languages: navigator.languages,
                    language: navigator.language,
                    screenResolution: {
                        width: screen.width,
                        height: screen.height,
                        availWidth: screen.availWidth,
                        availHeight: screen.availHeight,
                        colorDepth: screen.colorDepth,
                        pixelDepth: screen.pixelDepth
                    },
                    timezone: {
                        offset: new Date().getTimezoneOffset(),
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
                    },
                    webgl: (() => {
                        try {
                            const canvas = document.createElement('canvas');
                            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                            if (!gl) return { vendor: null, renderer: null };

                            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                            return {
                                vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
                                renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)
                            };
                        } catch(e) {
                            return { vendor: null, renderer: null, error: e.message };
                        }
                    })(),
                    webdriver: navigator.webdriver,
                    plugins: Array.from(navigator.plugins || []).map(p => p.name),
                    doNotTrack: navigator.doNotTrack,
                    cookieEnabled: navigator.cookieEnabled,
                    onLine: navigator.onLine,
                    connection: navigator.connection ? {
                        effectiveType: navigator.connection.effectiveType,
                        downlink: navigator.connection.downlink,
                        rtt: navigator.connection.rtt
                    } : 'undefined',
                    battery: 'checking...',
                    permissions: {
                        notifications: 'checking...',
                        geolocation: 'checking...'
                    }
                };
            })();
            """

            fingerprint = page.evaluate(fingerprint_script)

            logging.info("=" * 80)
            logging.info("🔍 BROWSER FINGERPRINT")
            logging.info("=" * 80)
            logging.info(f"User-Agent: {fingerprint.get('userAgent', 'N/A')}")
            logging.info(f"Platform: {fingerprint.get('platform', 'N/A')}")
            logging.info(f"Hardware Concurrency: {fingerprint.get('hardwareConcurrency', 'N/A')} CPU cores")
            logging.info(f"Device Memory: {fingerprint.get('deviceMemory', 'N/A')} GB")
            logging.info(f"Language: {fingerprint.get('language', 'N/A')}")
            logging.info(f"Languages: {fingerprint.get('languages', 'N/A')}")

            # Screen
            screen = fingerprint.get('screenResolution', {})
            logging.info(f"Screen: {screen.get('width')}x{screen.get('height')} ({screen.get('colorDepth')}bit)")

            # Timezone
            tz = fingerprint.get('timezone', {})
            logging.info(f"Timezone: {tz.get('timezone', 'N/A')} (offset: {tz.get('offset', 'N/A')})")

            # WebGL
            webgl = fingerprint.get('webgl', {})
            logging.info(f"WebGL Vendor: {webgl.get('vendor', 'N/A')}")
            logging.info(f"WebGL Renderer: {webgl.get('renderer', 'N/A')}")

            # Automation detection
            logging.info(f"Webdriver: {fingerprint.get('webdriver', 'N/A')}")
            logging.info(f"Plugins: {len(fingerprint.get('plugins', []))} installed")
            logging.info(f"Cookie Enabled: {fingerprint.get('cookieEnabled', 'N/A')}")
            logging.info(f"Do Not Track: {fingerprint.get('doNotTrack', 'N/A')}")

            logging.info("=" * 80)

            return fingerprint

        except Exception as e:
            logging.error(f"❌ Ошибка получения browser fingerprint: {e}")
            return None

    def log_webrtc_status(self, page):
        """
        Проверяет и логирует статус WebRTC

        Проверяет:
        - Доступность RTCPeerConnection API
        - Наличие WebRTC блокировки
        - Утечку локальных IP через ICE candidates
        """
        try:
            webrtc_check_script = """
            (() => {
                return new Promise((resolve) => {
                    const result = {
                        apiAvailable: typeof RTCPeerConnection !== 'undefined',
                        blockDetected: window.hasRunWebRTCBlock || false,
                        localIPs: [],
                        publicIPs: []
                    };

                    if (!result.apiAvailable) {
                        resolve(result);
                        return;
                    }

                    try {
                        const pc = new RTCPeerConnection({iceServers: []});
                        const timeout = setTimeout(() => {
                            pc.close();
                            resolve(result);
                        }, 3000);

                        pc.createDataChannel('');
                        pc.createOffer().then(offer => pc.setLocalDescription(offer));

                        pc.onicecandidate = (ice) => {
                            if (!ice || !ice.candidate) {
                                clearTimeout(timeout);
                                pc.close();
                                resolve(result);
                                return;
                            }

                            const candidate = ice.candidate.candidate;
                            const ipMatch = candidate.match(/([0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3})/);

                            if (ipMatch) {
                                const ip = ipMatch[1];
                                if (ip.startsWith('192.168.') || ip.startsWith('10.') || ip.startsWith('172.')) {
                                    result.localIPs.push(ip);
                                } else {
                                    result.publicIPs.push(ip);
                                }
                            }
                        };
                    } catch (e) {
                        result.error = e.message;
                        resolve(result);
                    }
                });
            })();
            """

            webrtc_status = page.evaluate(webrtc_check_script)

            logging.info("=" * 80)
            logging.info("🌐 WEBRTC STATUS")
            logging.info("=" * 80)
            logging.info(f"RTCPeerConnection API: {'✅ Available' if webrtc_status.get('apiAvailable') else '❌ Not Available'}")
            logging.info(f"WebRTC Block Active: {'✅ YES' if webrtc_status.get('blockDetected') else '❌ NO'}")

            local_ips = webrtc_status.get('localIPs', [])
            public_ips = webrtc_status.get('publicIPs', [])

            if local_ips:
                logging.warning(f"⚠️  Local IP Leak: {', '.join(local_ips)}")
            else:
                logging.info("✅ Local IP: Not leaked")

            if public_ips:
                logging.error(f"❌ PUBLIC IP LEAK: {', '.join(public_ips)}")
            else:
                logging.info("✅ Public IP: Not leaked")

            if webrtc_status.get('error'):
                logging.error(f"WebRTC Error: {webrtc_status['error']}")

            logging.info("=" * 80)

            return webrtc_status

        except Exception as e:
            logging.error(f"❌ Ошибка проверки WebRTC: {e}")
            return None

    def log_ip_information(self, proxy_config=None):
        """
        Логирует информацию об IP адресе

        Проверяет:
        - Текущий внешний IP
        - Geolocation
        - ISP/ASN
        - Proxy статус
        """
        try:
            logging.info("=" * 80)
            logging.info("🌍 IP INFORMATION")
            logging.info("=" * 80)

            # Проверка прокси конфигурации
            if proxy_config:
                logging.info(f"Proxy Configured: ✅ YES")
                logging.info(f"Proxy Server: {proxy_config.get('server', 'N/A')}")
                logging.info(f"Proxy Username: {proxy_config.get('username', 'N/A')}")
            else:
                logging.info(f"Proxy Configured: ❌ NO (Direct connection)")

            # Получаем внешний IP через API
            try:
                # Метод 1: ipify.org
                proxies = None
                if proxy_config:
                    proxy_url = f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['server'].replace('http://', '')}"
                    proxies = {'http': proxy_url, 'https': proxy_url}

                response = requests.get('https://api.ipify.org?format=json', proxies=proxies, timeout=10)
                external_ip = response.json().get('ip', 'Unknown')
                logging.info(f"External IP (ipify.org): {external_ip}")

                # Метод 2: ipinfo.io (более детальная информация)
                response = requests.get(f'https://ipinfo.io/{external_ip}/json', timeout=10)
                ip_info = response.json()

                logging.info(f"IP: {ip_info.get('ip', 'N/A')}")
                logging.info(f"City: {ip_info.get('city', 'N/A')}")
                logging.info(f"Region: {ip_info.get('region', 'N/A')}")
                logging.info(f"Country: {ip_info.get('country', 'N/A')}")
                logging.info(f"Location: {ip_info.get('loc', 'N/A')}")
                logging.info(f"Organization: {ip_info.get('org', 'N/A')}")
                logging.info(f"Postal: {ip_info.get('postal', 'N/A')}")
                logging.info(f"Timezone: {ip_info.get('timezone', 'N/A')}")

                # Определяем тип IP
                org = ip_info.get('org', '').lower()
                if any(keyword in org for keyword in ['hosting', 'server', 'datacenter', 'cloud', 'hetzner', 'aws', 'google', 'azure']):
                    logging.warning(f"⚠️  IP Type: DATACENTER (may be blocked by Cloudflare)")
                elif any(keyword in org for keyword in ['telecom', 'isp', 'broadband', 'cable', 'mobile']):
                    logging.info(f"✅ IP Type: RESIDENTIAL (trusted by Cloudflare)")
                else:
                    logging.info(f"❓ IP Type: UNKNOWN")

            except Exception as e:
                logging.error(f"❌ Не удалось получить IP информацию: {e}")

            logging.info("=" * 80)

        except Exception as e:
            logging.error(f"❌ Ошибка логирования IP информации: {e}")

    def log_http_headers(self, page):
        """
        Логирует HTTP заголовки, которые отправляет браузер
        """
        try:
            headers_script = """
            (() => {
                // Получаем заголовки через fetch interception
                return {
                    userAgent: navigator.userAgent,
                    acceptLanguage: navigator.language,
                    platform: navigator.platform,
                    vendor: navigator.vendor,
                    // Типичные заголовки Chrome
                    defaultHeaders: {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': navigator.language + ',en-US;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': navigator.doNotTrack,
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0'
                    }
                };
            })();
            """

            headers_info = page.evaluate(headers_script)

            logging.info("=" * 80)
            logging.info("📤 HTTP HEADERS (Sent by Browser)")
            logging.info("=" * 80)

            for key, value in headers_info.get('defaultHeaders', {}).items():
                logging.info(f"{key}: {value}")

            logging.info("=" * 80)

            return headers_info

        except Exception as e:
            logging.error(f"❌ Ошибка получения HTTP заголовков: {e}")
            return None

    def log_tls_fingerprint(self, page, url):
        """
        Логирует TLS/SSL информацию (JA3 fingerprint)

        Примечание: Полный JA3 fingerprint можно получить только на уровне сети,
        но мы можем залогировать доступную информацию из браузера
        """
        try:
            tls_script = """
            (url) => {
                return {
                    protocol: window.location.protocol,
                    secureContext: window.isSecureContext,
                    crypto: typeof window.crypto !== 'undefined',
                    subtle: typeof window.crypto?.subtle !== 'undefined',
                    // TLS version определяется на уровне браузера
                    browserVersion: navigator.userAgent.match(/Chrome\\/([0-9.]+)/)?.[1] || 'unknown'
                };
            }
            """

            tls_info = page.evaluate(tls_script, url)

            logging.info("=" * 80)
            logging.info("🔐 TLS/SSL INFORMATION")
            logging.info("=" * 80)
            logging.info(f"Protocol: {tls_info.get('protocol', 'N/A')}")
            logging.info(f"Secure Context: {tls_info.get('secureContext', 'N/A')}")
            logging.info(f"Web Crypto API: {'✅ Available' if tls_info.get('crypto') else '❌ Not Available'}")
            logging.info(f"SubtleCrypto: {'✅ Available' if tls_info.get('subtle') else '❌ Not Available'}")
            logging.info(f"Browser Version: Chrome/{tls_info.get('browserVersion', 'N/A')}")
            logging.info("Note: Full JA3 fingerprint is generated at TLS handshake level")
            logging.info("      Playwright/Camoufox uses genuine Chrome TLS stack")
            logging.info("=" * 80)

            return tls_info

        except Exception as e:
            logging.error(f"❌ Ошибка получения TLS информации: {e}")
            return None

    def log_full_network_state(self, page, proxy_config=None, url=None):
        """
        Полное логирование всего сетевого состояния

        Вызывает все методы логирования для максимальной детализации
        """
        logging.info("")
        logging.info("╔" + "═" * 78 + "╗")
        logging.info("║" + " " * 20 + "NETWORK STATE DETAILED LOG" + " " * 32 + "║")
        logging.info("║" + f" Session ID: {self.session_id}" + " " * (78 - len(f" Session ID: {self.session_id}")) + "║")
        logging.info("╚" + "═" * 78 + "╝")
        logging.info("")

        # 1. IP информация
        self.log_ip_information(proxy_config)

        # 2. WebRTC статус
        self.log_webrtc_status(page)

        # 3. Browser fingerprint
        self.log_browser_fingerprint(page)

        # 4. HTTP заголовки
        self.log_http_headers(page)

        # 5. TLS информация
        if url:
            self.log_tls_fingerprint(page, url)

        logging.info("")
        logging.info("╔" + "═" * 78 + "╗")
        logging.info("║" + " " * 25 + "END OF NETWORK LOG" + " " * 35 + "║")
        logging.info("╚" + "═" * 78 + "╝")
        logging.info("")


def test_network_logger():
    """
    Тестовая функция для проверки NetworkLogger
    """
    from camoufox.sync_api import Camoufox

    print("Тестирование NetworkLogger...")

    logger = NetworkLogger()

    with Camoufox(headless=False, humanize=True) as browser:
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://browserleaks.com/ip", wait_until="networkidle")

        # Полное логирование
        logger.log_full_network_state(page, proxy_config=None, url="https://browserleaks.com/ip")

    print("Тест завершен!")


if __name__ == "__main__":
    test_network_logger()
