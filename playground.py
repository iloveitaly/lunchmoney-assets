from camoufox.sync_api import Camoufox
from proxies import get_random_proxy

# solve the captcha? https://deepwiki.com/lixibi/browser-use/3.5-captcha-solving
# https://github.com/daijro/camoufox/issues/222
with Camoufox(proxy=get_random_proxy(), geoip=True, debug=True, block_webrtc=True) as browser:
  page = browser.new_page()
  breakpoint()

# https://2captcha.com this can be integrated into playwright 
# https://docs.capsolver.com/en/guide/api-server/