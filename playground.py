from camoufox.sync_api import Camoufox
from proxies import get_random_proxy

with Camoufox(proxy=get_random_proxy(), geoip=True) as browser:
  page = browser.new_page()
  breakpoint()