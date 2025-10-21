import os, sys, webbrowser, threading, time
from streamlit.web import bootstrap
from streamlit import config as _config

# --- clear any dev-mode vars ---
for k in list(os.environ.keys()):
    if k.startswith("STREAMLIT_"):
        del os.environ[k]

# --- clean server/browser config ---
_config.set_option("server.headless", True)
_config.set_option("server.port", 8502)
_config.set_option("server.enableCORS", True)
_config.set_option("server.enableXsrfProtection", True)
_config.set_option("browser.serverAddress", "localhost")
_config.set_option("browser.serverPort", 8502)
_config.set_option("browser.gatherUsageStats", False)
try:
    _config.set_option("global.developmentMode", False)
except Exception:
    pass

def resource_path(rel_path: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)
    return os.path.join(base, rel_path)

APP_FILE = resource_path("app_single.py")

# --- open browser automatically after a short delay ---
def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8502", new=1)

threading.Thread(target=open_browser, daemon=True).start()

# --- run streamlit normally ---
bootstrap.run(APP_FILE, "", [], {})

