import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import os
import re
import time
import random
import requests
import ssl
import socket
import certifi
import json
import itertools
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

# ── Termux / Android SSL fix ──────────────────────────────
# Termux often resets SSL connections to Telegram servers.
# This disables strict SSL verification so polling works.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# Patch telebot's internal requests session to skip SSL verify
import telebot.apihelper as _apihelper
_tg_session = requests.Session()
_tg_session.verify = False
_apihelper.SESSION = _tg_session

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = '8649575787:AAFgM8Eb5dVaumlTNTMzYxtu1eY3sN4YfkQ'
ADMIN_IDS = set([8671204957])  # Add admin Telegram user IDs here, e.g. set([123456789])

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

def is_admin(uid):
    # If ADMIN_IDS is empty, allow everyone (first-run mode)
    if not ADMIN_IDS:
        return True
    return uid in ADMIN_IDS

# ============================================================
# SESSION STATE (per admin)
# ============================================================
sessions = {}
session_lock = threading.Lock()

def get_session(cid):
    with session_lock:
        if cid not in sessions:
            sessions[cid] = {
                'server': 'limited.facebook.com',
                'device': 'Random',
                'browser': 'Chrome',
                'threads': 100,
                'proxy_list': [],
                'numbers': [],
                'running': False,
                'stop_flag': False,
                'stats': {'checked': 0, 'found': 0, 'not_found': 0, 'error': 0},
                'progress_msg_id': None,
                'found_numbers': [],
                'not_found_numbers': [],
                'error_numbers': [],
                'awaiting': None,
            }
        return sessions[cid]

# ============================================================
# CORE DATA
# ============================================================
SERVER_MAP = {
    '1': 'm.facebook.com',
    '2': 'mbasic.facebook.com',
    '3': 'touch.facebook.com',
    '4': 'free.facebook.com',
    '5': 'm.alpha.facebook.com',
    '6': 'm.beta.facebook.com',
    '7': 'x.facebook.com',
    '8': 'limited.facebook.com',
    '0': 'Random',
}

DEVICE_MAP = {
    '1': 'Android',
    '2': 'iPhone',
    '3': 'KaiOS',
    '4': 'Windows Phone',
    '5': 'BlackBerry',
    '0': 'Random',
}

BROWSER_MAP = {
    '1': 'Chrome', '2': 'Firefox', '3': 'Opera', '4': 'Edge', '5': 'Brave',
    '6': 'Samsung', '7': 'UC', '8': 'DuckDuckGo', '9': 'Vivaldi', '10': 'Yandex',
    '11': 'Kiwi', '12': 'Dolphin', '13': 'Mi Browser', '14': 'Maxthon', '15': 'Puffin',
    '0': 'Random',
}

COUNTRY_TO_LOCALE = {
    'AD': 'ca_ES', 'AE': 'ar_AR', 'AF': 'fa_IR', 'AG': 'en_US', 'AL': 'sq_AL',
    'AM': 'hy_AM', 'AO': 'pt_PT', 'AR': 'es_LA', 'AT': 'de_DE', 'AU': 'en_US',
    'AZ': 'az_AZ', 'BA': 'bs_BA', 'BB': 'en_US', 'BD': 'bn_IN', 'BE': 'nl_BE',
    'BF': 'fr_FR', 'BG': 'bg_BG', 'BH': 'ar_AR', 'BI': 'fr_FR', 'BJ': 'fr_FR',
    'BN': 'ms_MY', 'BO': 'es_LA', 'BR': 'pt_BR', 'BS': 'en_US', 'BT': 'en_US',
    'BW': 'en_US', 'BY': 'be_BY', 'BZ': 'en_US', 'CA': 'en_US', 'CD': 'fr_FR',
    'CF': 'fr_FR', 'CG': 'fr_FR', 'CH': 'de_DE', 'CI': 'fr_FR', 'CL': 'es_LA',
    'CM': 'fr_FR', 'CN': 'zh_CN', 'CO': 'es_LA', 'CR': 'es_LA', 'CU': 'es_LA',
    'CV': 'pt_PT', 'CY': 'el_GR', 'CZ': 'cs_CZ', 'DE': 'de_DE', 'DJ': 'fr_FR',
    'DK': 'da_DK', 'DM': 'en_US', 'DO': 'es_LA', 'DZ': 'ar_AR', 'EC': 'es_LA',
    'EE': 'et_EE', 'EG': 'ar_AR', 'ES': 'es_ES', 'ET': 'en_US', 'FI': 'fi_FI',
    'FJ': 'en_US', 'FR': 'fr_FR', 'GA': 'fr_FR', 'GB': 'en_GB', 'GE': 'ka_GE',
    'GH': 'en_US', 'GM': 'en_US', 'GN': 'fr_FR', 'GQ': 'es_LA', 'GR': 'el_GR',
    'GT': 'es_LA', 'GW': 'pt_PT', 'GY': 'en_US', 'HK': 'zh_HK', 'HN': 'es_LA',
    'HR': 'hr_HR', 'HT': 'fr_FR', 'HU': 'hu_HU', 'ID': 'id_ID', 'IE': 'en_GB',
    'IL': 'he_IL', 'IN': 'hi_IN', 'IQ': 'ar_AR', 'IR': 'fa_IR', 'IS': 'is_IS',
    'IT': 'it_IT', 'JM': 'en_US', 'JO': 'ar_AR', 'JP': 'ja_JP', 'KE': 'en_US',
    'KG': 'ky_KG', 'KH': 'km_KH', 'KM': 'fr_FR', 'KP': 'ko_KR', 'KR': 'ko_KR',
    'KW': 'ar_AR', 'KZ': 'kk_KZ', 'LA': 'en_US', 'LB': 'ar_AR', 'LI': 'de_DE',
    'LK': 'si_LK', 'LR': 'en_US', 'LS': 'en_US', 'LT': 'lt_LT', 'LU': 'fr_FR',
    'LV': 'lv_LV', 'LY': 'ar_AR', 'MA': 'ar_AR', 'MC': 'fr_FR', 'MD': 'ro_RO',
    'ME': 'sr_RS', 'MG': 'fr_FR', 'MK': 'mk_MK', 'ML': 'fr_FR', 'MM': 'my_MM',
    'MN': 'mn_MN', 'MR': 'ar_AR', 'MT': 'en_GB', 'MU': 'en_US', 'MV': 'en_US',
    'MW': 'en_US', 'MX': 'es_LA', 'MY': 'ms_MY', 'MZ': 'pt_PT', 'NA': 'en_US',
    'NE': 'fr_FR', 'NG': 'en_US', 'NI': 'es_LA', 'NL': 'nl_NL', 'NO': 'nb_NO',
    'NP': 'ne_NP', 'NZ': 'en_US', 'OM': 'ar_AR', 'PA': 'es_LA', 'PE': 'es_LA',
    'PH': 'en_US', 'PK': 'ur_PK', 'PL': 'pl_PL', 'PS': 'ar_AR', 'PT': 'pt_PT',
    'PY': 'es_LA', 'QA': 'ar_AR', 'RO': 'ro_RO', 'RS': 'sr_RS', 'RU': 'ru_RU',
    'RW': 'fr_FR', 'SA': 'ar_AR', 'SC': 'fr_FR', 'SD': 'ar_AR', 'SE': 'sv_SE',
    'SG': 'en_US', 'SI': 'sl_SI', 'SK': 'sk_SK', 'SL': 'en_US', 'SM': 'it_IT',
    'SN': 'fr_FR', 'SO': 'so_SO', 'SR': 'nl_NL', 'SS': 'en_US', 'ST': 'pt_PT',
    'SV': 'es_LA', 'SY': 'ar_AR', 'SZ': 'en_US', 'TD': 'fr_FR', 'TG': 'fr_FR',
    'TH': 'th_TH', 'TJ': 'tg_TJ', 'TL': 'pt_PT', 'TM': 'tk_TM', 'TN': 'ar_AR',
    'TO': 'en_US', 'TR': 'tr_TR', 'TT': 'en_US', 'TW': 'zh_TW', 'TZ': 'en_US',
    'UA': 'uk_UA', 'UG': 'en_US', 'US': 'en_US', 'UY': 'es_LA', 'UZ': 'uz_UZ',
    'VA': 'it_IT', 'VE': 'es_LA', 'VN': 'vi_VN', 'YE': 'ar_AR', 'ZA': 'en_US',
    'ZM': 'en_US', 'ZW': 'en_US',
}

def get_locale_code(cc):
    return COUNTRY_TO_LOCALE.get(cc.upper(), 'en_US')

# ============================================================
# PROXY & IP HELPERS
# ============================================================
free_proxies_cache = []
proxy_cache_lock = threading.Lock()

def fetch_new_ip():
    global free_proxies_cache
    with proxy_cache_lock:
        if not free_proxies_cache:
            try:
                r = requests.get(
                    'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=all',
                    timeout=10
                )
                free_proxies_cache = [p.strip() for p in r.text.strip().split('\n') if p.strip()]
                random.shuffle(free_proxies_cache)
            except:
                pass
        if free_proxies_cache:
            px = free_proxies_cache.pop(0)
            return {'http': f'http://{px}', 'https': f'http://{px}'}
    return None

def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    if '://' not in proxy_str:
        if '@' in proxy_str:
            part1, part2 = proxy_str.split('@', 1)
            if '.' in part2.split(':')[0]:
                proxy_url = f'http://{part1}@{part2}'
            else:
                proxy_url = f'http://{part2}@{part1}'
        else:
            parts = proxy_str.split(':')
            if len(parts) == 4:
                if '.' in parts[0]:
                    ip, port, user, pwd = parts
                    proxy_url = f'http://{user}:{pwd}@{ip}:{port}'
                else:
                    user, pwd, ip, port = parts
                    proxy_url = f'http://{user}:{pwd}@{ip}:{port}'
            elif len(parts) == 2:
                proxy_url = f'http://{parts[0]}:{parts[1]}'
            else:
                return None
    else:
        proxy_url = proxy_str
    return {'http': proxy_url, 'https': proxy_url}

def test_proxy(proxies, domain='limited.facebook.com'):
    try:
        r = requests.get(f'https://{domain}', proxies=proxies, timeout=10)
        return r.status_code == 200
    except:
        return False

def get_ip_info(proxies=None):
    try:
        r = requests.get('http://ip-api.com/json/', proxies=proxies, timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {
                'country': d.get('country', 'Unknown'),
                'countryCode': d.get('countryCode', 'US'),
                'timezone': d.get('timezone', 'Unknown'),
            }
    except:
        pass
    return {'country': 'Unknown', 'countryCode': 'US', 'timezone': 'Unknown'}

# ============================================================
# CORE: FACEBOOK CHECKER
# ============================================================
def process_sms(session, resp_text, number, url, base_headers, server_domain, sms_proxy_iterator=None, device_type='Android'):
    if 'id="contact_point_selector_form"' in resp_text and 'name="recover_method"' in resp_text:
        sms_options = re.findall(
            'input type="radio" name="recover_method" value="(send_sms:.*?)".*?id="(.*?)"', resp_text
        )
        if sms_options:
            return True
        else:
            return True
    return False

def check(number, proxy=None, locale='en_US', browser_type='Chrome', retry_count=0,
          server_domain='limited.facebook.com', sms_proxy_iterator=None, device_type='Random'):
    if server_domain == 'Random':
        server_domain = random.choice(list(v for k, v in SERVER_MAP.items() if v != 'Random'))

    session = requests.Session()
    session.timeout = 30
    if proxy:
        session.proxies.update(proxy)

    if device_type == 'Random':
        device_type = random.choice(['Android', 'iPhone'])

    if device_type == 'Android':
        andro_ver = random.choice(['10', '11', '12', '13', '14'])
        model = random.choice(['SM-G998B', 'SM-S908B', 'Pixel 6', 'Pixel 7', 'M2101K6G'])
        chrome_ver = random.randint(90, 122)
        ua = f'Mozilla/5.0 (Linux; Android {andro_ver}; {model}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver}.0.0.0 Mobile Safari/537.36'
    elif device_type == 'iPhone':
        ios_ver = random.choice(['15_6_1', '16_0', '16_2', '16_5', '17_0', '17_1'])
        ios_main = ios_ver.split('_')[0]
        ua = f'Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{ios_main}.0 Mobile/15E148 Safari/604.1'
    elif device_type == 'KaiOS':
        ua = f'Mozilla/5.0 (Mobile; Nokia; rv:48.0) Gecko/48.0 Firefox/48.0 KaiOS/{random.choice(["2.5","3.0","3.1"])}'
    elif device_type == 'Windows Phone':
        ua = f'Mozilla/5.0 (Windows Phone 10.0; Android 7.0; Microsoft; Lumia 950) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Mobile Safari/537.36 Edge/15.15063'
    elif device_type == 'BlackBerry':
        ua = f'Mozilla/5.0 (BB10; Touch) AppleWebKit/537.10+ (KHTML, like Gecko) Version/10.0.0.1337 Mobile Safari/537.10+'
    else:
        model = random.choice(['SM-G998B', 'Pixel 6', 'M2101K6G'])
        ua = f'Mozilla/5.0 (Linux; Android 12; {model}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(90,120)}.0.0.0 Mobile Safari/537.36'

    base_headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': f'{locale},en;q=0.9',
        'user-agent': ua,
        'upgrade-insecure-requests': '1',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'cache-control': 'max-age=0',
    }

    try:
        git_fb = session.get(
            f'https://{server_domain}/login/identify/?ctx=recover&ars=facebook_login&from_login_screen=0&__mmr=1&_rdr',
            headers=base_headers, timeout=30
        )
        try:
            lsd = re.search('name="lsd" value="(.*?)"', git_fb.text).group(1)
        except:
            try:
                lsd = re.search(r'\["LSD",\[\],\{"token":"(.*?)"\}', git_fb.text).group(1)
            except:
                lsd = ''
        try:
            jazoest = re.search('name="jazoest" value="(.*?)"', git_fb.text).group(1)
        except:
            try:
                jazoest = re.search('"initSprinkleValue":"(.*?)"', git_fb.text).group(1)
            except:
                jazoest = ''

        if not lsd or not jazoest:
            if retry_count < 3:
                new_proxy = fetch_new_ip()
                time.sleep(random.uniform(0.3, 0.8))
                return check(number, new_proxy or proxy, locale, browser_type, retry_count + 1, server_domain, sms_proxy_iterator, device_type)
            else:
                return 'error', 'IP Rate Limited'

        time.sleep(random.uniform(0.1, 0.3))
        _data = {'lsd': lsd, 'jazoest': jazoest, 'email': number, 'did_submit': 'Search'}
        post_headers = base_headers.copy()
        post_headers.update({
            'content-type': 'application/x-www-form-urlencoded',
            'origin': f'https://{server_domain}',
            'referer': f'https://{server_domain}/login/identify/?ctx=recover&ars=facebook_login&from_login_screen=0',
            'sec-fetch-site': 'same-origin',
        })
        url = f'https://{server_domain}/login/identify/?ctx=recover&c=%2Flogin%2F&search_attempts=1&ars=facebook_login&alternate_search=0'
        resp = session.post(url, data=_data, headers=post_headers, allow_redirects=True, timeout=30)

        if 'id="login_identify_search_error_msg"' in resp.text:
            err_match = re.search('id="login_identify_search_error_msg"[^>]*>(.*?)</div>', resp.text, re.IGNORECASE | re.DOTALL)
            err_text = err_match.group(1).lower() if err_match else ''
            if any(k in err_text for k in ['temporarily blocked', 'try again', 'too many', 'limit', 'spam', 'unusual', 'restrict']):
                if retry_count < 3:
                    new_proxy = fetch_new_ip()
                    return check(number, new_proxy or proxy, locale, browser_type, retry_count + 1, server_domain, sms_proxy_iterator, device_type)
                return 'error', 'Soft Ban'
            return 'not_found', 'Account Not Found'

        if 'action="/login/identify/?ctx=recover' in resp.text:
            return 'found', 'Multiple Accounts Found'

        if resp.url.startswith(f'https://{server_domain}/login/account_recovery/name_search/'):
            resp2 = session.get(resp.url, headers=base_headers, timeout=30)
            if 'action="/login/account_recovery/name_search/?flow=initiate_view' in resp2.text:
                resp3 = session.get(
                    f'https://{server_domain}/recover/initiate/?c=%2Flogin%2F&fl=initiate_view&ctx=msite_initiate_view',
                    headers=base_headers, timeout=30
                )
                if process_sms(session, resp3.text, number, resp3.url, base_headers, server_domain, sms_proxy_iterator, device_type):
                    return 'found', 'Account Found (SMS Option)'
                return 'found', 'Account Found (Other Option)'

        if resp.url.startswith(f'https://{server_domain}/login/device-based/ar/login/?ldata='):
            resp2 = session.get(resp.url, headers=base_headers, timeout=30)
            if 'id="contact_point_selector_form"' in resp2.text:
                if process_sms(session, resp2.text, number, resp2.url, base_headers, server_domain, sms_proxy_iterator, device_type):
                    return 'found', 'Account Found (SMS Option)'
                return 'found', 'Account Found (Contact Point)'
            if 'name="captcha_response"' in resp2.text:
                return 'not_found', 'Captcha Block'
            if '/help/121104481304395' in resp2.text or '/help/103873106370583' in resp2.text:
                return 'found', 'Account Disabled (Found)'
            return 'error', 'Unknown Page'

        if 'window.MPageLoadClientMetrics' in resp.text:
            if retry_count < 3:
                new_proxy = fetch_new_ip()
                return check(number, new_proxy or proxy, locale, browser_type, retry_count + 1, server_domain, sms_proxy_iterator, device_type)
            return 'error', 'Bot Block'

        return 'error', 'Unknown Response'

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        if retry_count < 3:
            time.sleep(2)
            new_proxy = fetch_new_ip()
            return check(number, new_proxy or proxy, locale, browser_type, retry_count + 1, server_domain, sms_proxy_iterator, device_type)
        return 'error', 'Network Error'
    except Exception as e:
        return 'error', str(e)[:50]

# ============================================================
# EXTRACT NUMBERS FROM EXCEL
# ============================================================
def extract_numbers_from_excel(path):
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb.active
        target_col = None
        max_matches = 0
        for col_idx in range(1, sheet.max_column + 1):
            match_count = 0
            for row_idx in range(2, min(22, sheet.max_row + 1)):
                val = sheet.cell(row=row_idx, column=col_idx).value
                if val:
                    s = re.sub(r'[\s\-\(\)\+]', '', str(val).strip())
                    if s.isdigit() and 7 <= len(s) <= 15:
                        match_count += 1
            if match_count > max_matches:
                max_matches = match_count
                target_col = col_idx
        if not target_col:
            return None, 'No phone column found'
        numbers = []
        for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=target_col, max_col=target_col, values_only=True):
            val = row[0]
            if val:
                s = re.sub(r'[\s\-\(\)\+]', '', str(val).strip())
                if s.isdigit() and 7 <= len(s) <= 15:
                    numbers.append(s)
        return numbers, None
    except Exception as e:
        return None, str(e)

# ============================================================
# BACKGROUND CHECKER THREAD
# ============================================================
def safe_send(chat_id, text, reply_markup=None, retries=5):
    """Send message with auto-retry on network errors."""
    for attempt in range(retries):
        try:
            return bot.send_message(chat_id, text, reply_markup=reply_markup)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                print(f"safe_send failed after {retries} attempts: {e}")
    return None

def safe_edit(chat_id, msg_id, text, reply_markup=None, retries=3):
    """Edit message with auto-retry on network errors."""
    for attempt in range(retries):
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
            return True
        except Exception as e:
            err = str(e)
            # Message not modified is not a real error
            if 'message is not modified' in err.lower():
                return True
            if attempt < retries - 1:
                time.sleep(2)
    return False

def run_checker(cid, chat_id):
    s = get_session(cid)
    numbers = s['numbers']
    server = s['server']
    device = s['device']
    browser = s['browser']
    threads = s['threads']
    proxies = s['proxy_list']

    s['stats'] = {'checked': 0, 'found': 0, 'not_found': 0, 'error': 0}
    s['found_numbers'] = []
    s['not_found_numbers'] = []
    s['error_numbers'] = []

    proxy_iter = itertools.cycle(proxies) if proxies else None

    try:
        ip_info = get_ip_info(proxies[0] if proxies else None)
        locale = get_locale_code(ip_info['countryCode'])
    except:
        locale = 'en_US'

    total = len(numbers)
    last_update_time = time.time()

    def send_progress_update():
        st = s['stats']
        pct = int((st['checked'] / total) * 100) if total > 0 else 0
        filled = int(pct / 5)
        bar = '█' * filled + '░' * (20 - filled)
        text = (
            f"⚡ <b>Checking in Progress...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Progress : [{bar}] {pct}%\n"
            f"🔢 Checked  : <code>{st['checked']}/{total}</code>\n"
            f"✅ Found    : <code>{st['found']}</code>\n"
            f"❌ Not Found: <code>{st['not_found']}</code>\n"
            f"⚠️ Error    : <code>{st['error']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Server   : <code>{server}</code>\n"
            f"📱 Device   : <code>{device}</code>\n"
            f"🔑 Proxies  : <code>{len(proxies)}</code>"
        )
        stop_mk = InlineKeyboardMarkup()
        stop_mk.add(InlineKeyboardButton("🛑 Stop Checking", callback_data="stop_check"))
        if s['progress_msg_id']:
            ok = safe_edit(chat_id, s['progress_msg_id'], text, stop_mk)
            if not ok:
                msg = safe_send(chat_id, text, stop_mk)
                if msg:
                    s['progress_msg_id'] = msg.message_id
        else:
            msg = safe_send(chat_id, text, stop_mk)
            if msg:
                s['progress_msg_id'] = msg.message_id

    # Send initial status message (with retry)
    init_msg = safe_send(
        chat_id,
        f"🚀 <b>Starting FB Checker...</b>\n"
        f"📋 Numbers: <code>{total}</code>\n"
        f"🌐 Server : <code>{server}</code>\n"
        f"📱 Device : <code>{device}</code>\n"
        f"🔢 Threads: <code>{threads}</code>"
    )
    if init_msg:
        s['progress_msg_id'] = init_msg.message_id

    def worker(number):
        if s['stop_flag']:
            return
        proxy = next(proxy_iter) if proxy_iter else None
        try:
            result, msg_txt = check(
                number, proxy=proxy, locale=locale,
                server_domain=server, device_type=device
            )
        except Exception as e:
            result, msg_txt = 'error', str(e)[:30]

        with session_lock:
            s['stats']['checked'] += 1
            if result == 'found':
                s['stats']['found'] += 1
                s['found_numbers'].append(number)
            elif result == 'not_found':
                s['stats']['not_found'] += 1
                s['not_found_numbers'].append(number)
            else:
                s['stats']['error'] += 1
                s['error_numbers'].append(number)

    send_progress_update()

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(worker, num): num for num in numbers}
        for i, future in enumerate(as_completed(futures)):
            if s['stop_flag']:
                executor.shutdown(wait=False, cancel_futures=True)
                break
            now = time.time()
            if now - last_update_time >= 15 or (i + 1) % 100 == 0:
                send_progress_update()
                last_update_time = now

    s['running'] = False
    s['stop_flag'] = False

    # Save result files
    try:
        with open(f'found_{cid}.txt', 'w') as f:
            f.write('\n'.join(s['found_numbers']))
        with open(f'not_found_{cid}.txt', 'w') as f:
            f.write('\n'.join(s['not_found_numbers']))
    except:
        pass

    st = s['stats']
    pct = int((st['checked'] / total) * 100) if total > 0 else 0
    summary = (
        f"✅ <b>Checking Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 Total    : <code>{total}</code>\n"
        f"📊 Checked  : <code>{st['checked']}</code> ({pct}%)\n"
        f"✅ Found    : <code>{st['found']}</code>\n"
        f"❌ Not Found: <code>{st['not_found']}</code>\n"
        f"⚠️ Error    : <code>{st['error']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    result_mk = InlineKeyboardMarkup(row_width=2)
    result_mk.add(
        InlineKeyboardButton("📥 Download Found", callback_data="dl_found"),
        InlineKeyboardButton("📥 Download Not Found", callback_data="dl_not_found"),
    )
    result_mk.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))

    if s['progress_msg_id']:
        ok = safe_edit(chat_id, s['progress_msg_id'], summary, result_mk)
        if not ok:
            safe_send(chat_id, summary, result_mk)
    else:
        safe_send(chat_id, summary, result_mk)

# ============================================================
# UI BUILDERS
# ============================================================
def main_menu_text(cid):
    s = get_session(cid)
    status = "🟢 Running" if s['running'] else "🔴 Idle"
    return (
        f"🤖 <b>FB Forget Checker Bot</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Status  : {status}\n"
        f"🌐 Server  : <code>{s['server']}</code>\n"
        f"📱 Device  : <code>{s['device']}</code>\n"
        f"🌍 Browser : <code>{s['browser']}</code>\n"
        f"🔢 Threads : <code>{s['threads']}</code>\n"
        f"🔑 Proxies : <code>{len(s['proxy_list'])}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def main_menu_markup(cid):
    s = get_session(cid)
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("🚀 Start Check", callback_data="start_check"),
        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
    )
    mk.add(
        InlineKeyboardButton("📊 Live Stats", callback_data="live_stats"),
        InlineKeyboardButton("📁 Download Results", callback_data="download_results"),
    )
    if s['running']:
        mk.add(InlineKeyboardButton("🛑 Stop Checking", callback_data="stop_check"))
    return mk

def settings_markup():
    mk = InlineKeyboardMarkup(row_width=2)
    mk.add(
        InlineKeyboardButton("🌐 Server", callback_data="set_server"),
        InlineKeyboardButton("📱 Device", callback_data="set_device"),
    )
    mk.add(
        InlineKeyboardButton("🌍 Browser", callback_data="set_browser"),
        InlineKeyboardButton("🔢 Threads", callback_data="set_threads"),
    )
    mk.add(
        InlineKeyboardButton("🔑 Add Proxy", callback_data="set_proxy"),
        InlineKeyboardButton("🗑 Clear Proxy", callback_data="clear_proxy"),
    )
    mk.add(InlineKeyboardButton("🔄 Reset All Config", callback_data="reset_config"))
    mk.add(InlineKeyboardButton("🏠 Back to Menu", callback_data="main_menu"))
    return mk

def server_markup():
    mk = InlineKeyboardMarkup(row_width=2)
    for k, v in SERVER_MAP.items():
        label = "🎲 Random (Mix)" if v == 'Random' else v
        mk.add(InlineKeyboardButton(label, callback_data=f"sv_{k}"))
    mk.add(InlineKeyboardButton("🔙 Back", callback_data="settings"))
    return mk

def device_markup():
    mk = InlineKeyboardMarkup(row_width=2)
    labels = {'0': '🎲 Random', '1': '🤖 Android', '2': '🍎 iPhone',
              '3': '📱 KaiOS', '4': '🪟 Windows Phone', '5': '🫐 BlackBerry'}
    for k, label in labels.items():
        mk.add(InlineKeyboardButton(label, callback_data=f"dv_{k}"))
    mk.add(InlineKeyboardButton("🔙 Back", callback_data="settings"))
    return mk

def browser_markup():
    mk = InlineKeyboardMarkup(row_width=3)
    icons = {'0': '🎲 Random', '1': '🟡 Chrome', '2': '🦊 Firefox', '3': '🔴 Opera',
             '4': '💙 Edge', '5': '🦁 Brave', '6': '📱 Samsung', '7': '🟠 UC',
             '8': '🦆 DuckDuckGo', '9': '🟣 Vivaldi', '10': '🅨 Yandex',
             '11': '🥝 Kiwi', '12': '🐬 Dolphin', '13': '🔵 Mi Browser',
             '14': '⚡ Maxthon', '15': '🌊 Puffin'}
    btns = [InlineKeyboardButton(label, callback_data=f"br_{k}") for k, label in icons.items()]
    mk.add(*btns)
    mk.add(InlineKeyboardButton("🔙 Back", callback_data="settings"))
    return mk

# ============================================================
# HANDLERS
# ============================================================
@bot.message_handler(commands=['myid'])
def cmd_myid(message):
    uid = message.from_user.id
    bot.send_message(
        message.chat.id,
        f"🆔 <b>Your Telegram User ID:</b>\n<code>{uid}</code>\n\n"
        f"👉 checker_bot.py তে এই লাইনে এই ID বসাও:\n"
        f"<code>ADMIN_IDS = set([{uid}])</code>"
    )

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Access Denied.")
        return
    cid = message.chat.id
    get_session(cid)
    bot.send_message(cid, main_menu_text(cid), reply_markup=main_menu_markup(cid))

@bot.message_handler(content_types=['document'])
def handle_file(message):
    if not is_admin(message.from_user.id):
        return
    cid = message.chat.id
    s = get_session(cid)

    if s.get('awaiting') != 'file':
        return

    s['awaiting'] = None
    doc = message.document
    fname = doc.file_name or ''

    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.send_message(cid, f"❌ File download failed: {e}")
        return

    numbers = []
    if fname.endswith('.xlsx') or fname.endswith('.xls'):
        tmp_path = f'/tmp/numlist_{cid}.xlsx'
        with open(tmp_path, 'wb') as f:
            f.write(downloaded)
        numbers, err = extract_numbers_from_excel(tmp_path)
        if err:
            bot.send_message(cid, f"❌ Excel parse error: {err}")
            return
    elif fname.endswith('.txt'):
        try:
            content = downloaded.decode('utf-8', errors='ignore')
            numbers = [ln.strip() for ln in content.splitlines() if ln.strip()]
        except Exception as e:
            bot.send_message(cid, f"❌ Text file parse error: {e}")
            return
    else:
        bot.send_message(cid, "❌ Only <b>.txt</b> or <b>.xlsx</b> files are supported.")
        return

    if not numbers:
        bot.send_message(cid, "⚠️ No valid numbers found in the file.")
        return

    s['numbers'] = numbers
    bot.send_message(
        cid,
        f"✅ <b>File loaded!</b>\n"
        f"📋 Numbers found: <code>{len(numbers)}</code>\n\n"
        f"Ready to start. Use the button below.",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🚀 Start Now!", callback_data="begin_check")
        )
    )

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not is_admin(message.from_user.id):
        return
    cid = message.chat.id
    s = get_session(cid)
    text = message.text.strip()

    if s.get('awaiting') == 'threads':
        s['awaiting'] = None
        try:
            t = int(text)
            if not (1 <= t <= 2000):
                raise ValueError
            s['threads'] = t
            bot.send_message(cid, f"✅ Threads set to <code>{t}</code>", reply_markup=settings_markup())
        except:
            bot.send_message(cid, "❌ Invalid! Enter a number between 1–2000.", reply_markup=settings_markup())

    elif s.get('awaiting') == 'proxy':
        s['awaiting'] = None
        proxies_added = 0
        lines = text.strip().splitlines()
        wait_msg = bot.send_message(cid, f"⏳ Testing {len(lines)} proxy/proxies...")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parsed = parse_proxy(line)
            if parsed:
                if test_proxy(parsed, s['server']):
                    s['proxy_list'].append(parsed)
                    proxies_added += 1
        try:
            bot.edit_message_text(
                f"✅ <b>{proxies_added}/{len(lines)}</b> proxies added and working!\n"
                f"🔑 Total proxies: <code>{len(s['proxy_list'])}</code>",
                cid, wait_msg.message_id,
                reply_markup=settings_markup()
            )
        except:
            bot.send_message(cid, f"✅ {proxies_added} proxies added.", reply_markup=settings_markup())

    elif s.get('awaiting') == 'numbers_text':
        s['awaiting'] = None
        nums = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if nums:
            s['numbers'] = nums
            bot.send_message(
                cid,
                f"✅ <b>{len(nums)} numbers loaded!</b>",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🚀 Start Now!", callback_data="begin_check")
                )
            )
        else:
            bot.send_message(cid, "⚠️ No valid numbers found.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_admin(call.from_user.id):
        return

    cid = call.message.chat.id
    mid = call.message.message_id
    data = call.data
    s = get_session(cid)

    bot.answer_callback_query(call.id)

    # ── MAIN MENU ──
    if data == 'main_menu':
        try:
            bot.edit_message_text(main_menu_text(cid), cid, mid, reply_markup=main_menu_markup(cid))
        except:
            bot.send_message(cid, main_menu_text(cid), reply_markup=main_menu_markup(cid))

    # ── SETTINGS ──
    elif data == 'settings':
        s_txt = (
            f"⚙️ <b>Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Server  : <code>{s['server']}</code>\n"
            f"📱 Device  : <code>{s['device']}</code>\n"
            f"🌍 Browser : <code>{s['browser']}</code>\n"
            f"🔢 Threads : <code>{s['threads']}</code>\n"
            f"🔑 Proxies : <code>{len(s['proxy_list'])}</code>"
        )
        try:
            bot.edit_message_text(s_txt, cid, mid, reply_markup=settings_markup())
        except:
            bot.send_message(cid, s_txt, reply_markup=settings_markup())

    # ── SET SERVER ──
    elif data == 'set_server':
        try:
            bot.edit_message_text("🌐 <b>Select Server:</b>", cid, mid, reply_markup=server_markup())
        except:
            bot.send_message(cid, "🌐 <b>Select Server:</b>", reply_markup=server_markup())

    elif data.startswith('sv_'):
        key = data[3:]
        s['server'] = SERVER_MAP.get(key, 'limited.facebook.com')
        bot.answer_callback_query(call.id, f"✅ Server: {s['server']}", show_alert=True)
        try:
            bot.edit_message_text(
                f"⚙️ <b>Settings</b>\n🌐 Server: <code>{s['server']}</code>",
                cid, mid, reply_markup=settings_markup()
            )
        except:
            bot.send_message(cid, f"✅ Server set to <code>{s['server']}</code>", reply_markup=settings_markup())

    # ── SET DEVICE ──
    elif data == 'set_device':
        try:
            bot.edit_message_text("📱 <b>Select Device:</b>", cid, mid, reply_markup=device_markup())
        except:
            bot.send_message(cid, "📱 <b>Select Device:</b>", reply_markup=device_markup())

    elif data.startswith('dv_'):
        key = data[3:]
        s['device'] = DEVICE_MAP.get(key, 'Random')
        bot.answer_callback_query(call.id, f"✅ Device: {s['device']}", show_alert=True)
        try:
            bot.edit_message_text(
                f"⚙️ <b>Settings</b>\n📱 Device: <code>{s['device']}</code>",
                cid, mid, reply_markup=settings_markup()
            )
        except:
            bot.send_message(cid, f"✅ Device set to <code>{s['device']}</code>", reply_markup=settings_markup())

    # ── SET BROWSER ──
    elif data == 'set_browser':
        try:
            bot.edit_message_text("🌍 <b>Select Browser:</b>", cid, mid, reply_markup=browser_markup())
        except:
            bot.send_message(cid, "🌍 <b>Select Browser:</b>", reply_markup=browser_markup())

    elif data.startswith('br_'):
        key = data[3:]
        s['browser'] = BROWSER_MAP.get(key, 'Chrome')
        bot.answer_callback_query(call.id, f"✅ Browser: {s['browser']}", show_alert=True)
        try:
            bot.edit_message_text(
                f"⚙️ <b>Settings</b>\n🌍 Browser: <code>{s['browser']}</code>",
                cid, mid, reply_markup=settings_markup()
            )
        except:
            bot.send_message(cid, f"✅ Browser set to <code>{s['browser']}</code>", reply_markup=settings_markup())

    # ── SET THREADS ──
    elif data == 'set_threads':
        mk_t = InlineKeyboardMarkup(row_width=3)
        mk_t.add(
            InlineKeyboardButton("⚡ 50",   callback_data="th_50"),
            InlineKeyboardButton("🚀 100",  callback_data="th_100"),
            InlineKeyboardButton("💥 200",  callback_data="th_200"),
            InlineKeyboardButton("🔥 300",  callback_data="th_300"),
            InlineKeyboardButton("🌪 500",  callback_data="th_500"),
            InlineKeyboardButton("💣 750",  callback_data="th_750"),
            InlineKeyboardButton("🚀 1000", callback_data="th_1000"),
            InlineKeyboardButton("⚡ 1500", callback_data="th_1500"),
            InlineKeyboardButton("🔥 2000", callback_data="th_2000"),
        )
        mk_t.add(InlineKeyboardButton("✏️ Custom (type)", callback_data="th_custom"))
        mk_t.add(InlineKeyboardButton("🔙 Back", callback_data="settings"))
        txt = (
            f"🔢 <b>Set Thread Count</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Current : <code>{s['threads']}</code>\n"
            f"Range   : 1 – 2000\n\n"
            f"📌 <b>Recommended:</b>\n"
            f"• No Proxy      → 50–100\n"
            f"• With Proxy    → 300–500\n"
            f"• Many Proxies  → 1000–2000"
        )
        try:
            bot.edit_message_text(txt, cid, mid, reply_markup=mk_t)
        except:
            bot.send_message(cid, txt, reply_markup=mk_t)

    elif data.startswith('th_'):
        key = data[3:]
        if key == 'custom':
            s['awaiting'] = 'threads'
            try:
                bot.edit_message_text(
                    f"✏️ <b>Custom Thread Count</b>\n\nCurrent: <code>{s['threads']}</code>\nRange: 1–2000\n\nSend the number:",
                    cid, mid
                )
            except:
                bot.send_message(cid, "✏️ Send thread count (1–2000):")
        else:
            t = int(key)
            s['threads'] = t
            bot.answer_callback_query(call.id, f"✅ Threads set to {t}", show_alert=True)
            try:
                bot.edit_message_text(
                    f"⚙️ <b>Settings</b>\n🔢 Threads: <code>{t}</code>",
                    cid, mid, reply_markup=settings_markup()
                )
            except:
                bot.send_message(cid, f"✅ Threads set to <code>{t}</code>", reply_markup=settings_markup())

    # ── PROXY ──
    elif data == 'set_proxy':
        s['awaiting'] = 'proxy'
        try:
            bot.edit_message_text(
                "🔑 <b>Add Proxy</b>\n\nSend one or multiple proxies, one per line.\n"
                "Supported formats:\n"
                "<code>ip:port</code>\n"
                "<code>user:pass@ip:port</code>\n"
                "<code>http://user:pass@ip:port</code>",
                cid, mid
            )
        except:
            bot.send_message(
                cid,
                "✏️ Send proxy/proxies (one per line):\n"
                "<code>ip:port</code> or <code>user:pass@ip:port</code>"
            )

    elif data == 'clear_proxy':
        s['proxy_list'] = []
        bot.answer_callback_query(call.id, "✅ All proxies cleared!", show_alert=True)
        try:
            bot.edit_message_text(
                "⚙️ <b>Settings</b>\n🔑 Proxies: <code>0</code> (cleared)",
                cid, mid, reply_markup=settings_markup()
            )
        except:
            bot.send_message(cid, "✅ Proxies cleared.", reply_markup=settings_markup())

    # ── RESET CONFIG ──
    elif data == 'reset_config':
        mk_confirm = InlineKeyboardMarkup(row_width=2)
        mk_confirm.add(
            InlineKeyboardButton("✅ Yes, Reset", callback_data="reset_confirm"),
            InlineKeyboardButton("❌ Cancel",     callback_data="settings"),
        )
        try:
            bot.edit_message_text(
                "⚠️ <b>Reset All Settings?</b>\n\n"
                "This will reset:\n"
                "• Server → limited.facebook.com\n"
                "• Device → Random\n"
                "• Browser → Chrome\n"
                "• Threads → 100\n"
                "• Proxy → Clear all\n\n"
                "Numbers list will NOT be cleared.",
                cid, mid, reply_markup=mk_confirm
            )
        except:
            bot.send_message(cid, "⚠️ Confirm reset?", reply_markup=mk_confirm)

    elif data == 'reset_confirm':
        if s['running']:
            bot.answer_callback_query(call.id, "⚠️ Stop checking first!", show_alert=True)
            return
        sessions[cid] = {
            'server': 'limited.facebook.com',
            'device': 'Random',
            'browser': 'Chrome',
            'threads': 100,
            'proxy_list': [],
            'numbers': s.get('numbers', []),
            'running': False,
            'stop_flag': False,
            'stats': {'checked': 0, 'found': 0, 'not_found': 0, 'error': 0},
            'progress_msg_id': None,
            'found_numbers': [],
            'not_found_numbers': [],
            'error_numbers': [],
            'awaiting': None,
        }
        bot.answer_callback_query(call.id, "✅ All settings reset to default!", show_alert=True)
        s2 = get_session(cid)
        s_txt = (
            f"🔄 <b>Config Reset Done!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Server  : <code>{s2['server']}</code>\n"
            f"📱 Device  : <code>{s2['device']}</code>\n"
            f"🌍 Browser : <code>{s2['browser']}</code>\n"
            f"🔢 Threads : <code>{s2['threads']}</code>\n"
            f"🔑 Proxies : <code>0</code>"
        )
        try:
            bot.edit_message_text(s_txt, cid, mid, reply_markup=settings_markup())
        except:
            bot.send_message(cid, s_txt, reply_markup=settings_markup())

    # ── START CHECK ──
    elif data == 'start_check':
        if s['running']:
            bot.answer_callback_query(call.id, "⚠️ Already running! Stop first.", show_alert=True)
            return
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(
            InlineKeyboardButton("📁 Upload .txt or .xlsx File", callback_data="upload_file"),
            InlineKeyboardButton("✏️ Paste Numbers (Text)", callback_data="paste_numbers"),
        )
        if s.get('numbers'):
            mk.add(InlineKeyboardButton(f"▶️ Use Last List ({len(s['numbers'])} numbers)", callback_data="begin_check"))
        mk.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
        try:
            bot.edit_message_text("📂 <b>How to load numbers?</b>", cid, mid, reply_markup=mk)
        except:
            bot.send_message(cid, "📂 <b>How to load numbers?</b>", reply_markup=mk)

    elif data == 'upload_file':
        s['awaiting'] = 'file'
        try:
            bot.edit_message_text(
                "📤 <b>Send your file</b>\n\nSupported: <b>.txt</b> (one number per line) or <b>.xlsx</b>",
                cid, mid
            )
        except:
            bot.send_message(cid, "📤 Send your .txt or .xlsx file now:")

    elif data == 'paste_numbers':
        s['awaiting'] = 'numbers_text'
        try:
            bot.edit_message_text(
                "✏️ <b>Paste numbers</b>\n\nSend numbers, one per line:\n<code>9920000001\n9920000002\n...</code>",
                cid, mid
            )
        except:
            bot.send_message(cid, "✏️ Send numbers, one per line:")

    elif data == 'begin_check':
        if s['running']:
            bot.answer_callback_query(call.id, "⚠️ Already running!", show_alert=True)
            return
        if not s.get('numbers'):
            bot.answer_callback_query(call.id, "❌ No numbers loaded! Upload a file first.", show_alert=True)
            return
        s['running'] = True
        s['stop_flag'] = False
        s['progress_msg_id'] = None
        t = threading.Thread(target=run_checker, args=(cid, cid), daemon=True)
        t.start()

    # ── STOP ──
    elif data == 'stop_check':
        if s['running']:
            s['stop_flag'] = True
            bot.answer_callback_query(call.id, "🛑 Stop signal sent...", show_alert=True)
            try:
                bot.edit_message_text(
                    "⏹ <b>Stopping...</b>\nWaiting for current checks to finish.",
                    cid, mid
                )
            except:
                bot.send_message(cid, "⏹ Stopping...")
        else:
            bot.answer_callback_query(call.id, "ℹ️ Nothing is running.", show_alert=True)

    # ── LIVE STATS ──
    elif data == 'live_stats':
        st = s['stats']
        total = len(s['numbers']) if s['numbers'] else 0
        pct = int((st['checked'] / total) * 100) if total > 0 else 0
        status_txt = "🟢 Running" if s['running'] else "🔴 Idle"
        stats_text = (
            f"📊 <b>Live Stats</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Status    : {status_txt}\n"
            f"📋 Total     : <code>{total}</code>\n"
            f"🔢 Checked   : <code>{st['checked']}</code> ({pct}%)\n"
            f"✅ Found     : <code>{st['found']}</code>\n"
            f"❌ Not Found : <code>{st['not_found']}</code>\n"
            f"⚠️ Error     : <code>{st['error']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        mk = InlineKeyboardMarkup(row_width=2)
        mk.add(
            InlineKeyboardButton("🔄 Refresh", callback_data="live_stats"),
            InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
        )
        try:
            bot.edit_message_text(stats_text, cid, mid, reply_markup=mk)
        except:
            bot.send_message(cid, stats_text, reply_markup=mk)

    # ── DOWNLOAD RESULTS ──
    elif data == 'download_results':
        found_path = f'found_{cid}.txt'
        nf_path = f'not_found_{cid}.txt'
        has_found = os.path.exists(found_path) and os.path.getsize(found_path) > 0
        has_nf = os.path.exists(nf_path) and os.path.getsize(nf_path) > 0
        if not has_found and not has_nf:
            bot.answer_callback_query(call.id, "ℹ️ No results yet. Run a check first.", show_alert=True)
            return
        mk = InlineKeyboardMarkup(row_width=2)
        if has_found:
            mk.add(InlineKeyboardButton(f"✅ Found ({len(s['found_numbers'])})", callback_data="dl_found"))
        if has_nf:
            mk.add(InlineKeyboardButton(f"❌ Not Found ({len(s['not_found_numbers'])})", callback_data="dl_not_found"))
        mk.add(InlineKeyboardButton("🏠 Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text("📁 <b>Download Results:</b>", cid, mid, reply_markup=mk)
        except:
            bot.send_message(cid, "📁 <b>Download Results:</b>", reply_markup=mk)

    elif data == 'dl_found':
        path = f'found_{cid}.txt'
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, 'rb') as f:
                bot.send_document(cid, f, caption=f"✅ Found: <code>{len(s['found_numbers'])}</code> numbers")
        else:
            bot.answer_callback_query(call.id, "ℹ️ No found numbers yet.", show_alert=True)

    elif data == 'dl_not_found':
        path = f'not_found_{cid}.txt'
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, 'rb') as f:
                bot.send_document(cid, f, caption=f"❌ Not Found: <code>{len(s['not_found_numbers'])}</code> numbers")
        else:
            bot.answer_callback_query(call.id, "ℹ️ No not-found numbers yet.", show_alert=True)

# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    print("=" * 45)
    print("  ✅  FB Checker Bot is running!")
    print("  📌  /start  — Main menu")
    print("  📌  /myid   — Get your Telegram user ID")
    if not ADMIN_IDS:
        print("  ⚠️   ADMIN_IDS is empty — all users have access!")
        print("       Send /myid to bot, then set your ID.")
    else:
        print(f"  🔐  Admins: {ADMIN_IDS}")
    print("=" * 45)

    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=30,
                restart_on_change=False,
                skip_pending=True,
            )
        except Exception as e:
            print(f"⚠️ Polling error: {e} — restarting in 5s...")
            time.sleep(5)
