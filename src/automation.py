import os
import sys
import time
import argparse
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv

LOGIN_URL = "http://iris.tmoviles.com.ar/workspace/faces/jsf/workspace/workspace.xhtml"

# XPaths provided by the user
XPATHS = {
    "usuario": "/html/body/form/div/div/table/tbody/tr[2]/td[2]/div/div/div[1]/table/tbody/tr[1]/td[2]/input",
    "password": "/html/body/form/div/div/table/tbody/tr[2]/td[2]/div/div/div[1]/table/tbody/tr[2]/td[2]/input",
    "consulta_operacion": "/html/body/div/div/span/div/form/div[2]/div[13]/form/div[2]/div/span/table/tbody/tr/td/div[2]/form/div/span/div/table/tbody/tr[2]/td[2]/div/div/div/table/tbody/tr[5]/td/table/tbody/tr/td[2]/a/span",
    "dni_input": "/html/body/table/tbody/tr/td/center/div/form/div[2]/table/tbody/tr/td/div/table/tbody/tr[2]/td/div/table/tbody/tr/td/div/table/tbody/tr[2]/td[4]/div/input",
    "consultar_btn": "/html/body/table/tbody/tr/td/center/div/form/div[2]/table/tbody/tr/td/div/table/tbody/tr[3]/td/div/table/tbody/tr/td[7]/div/input",
    "estado_cell": "/html/body/table/tbody/tr/td/center/div/form/div[2]/div/table/tbody/tr/td/div/table/tbody/tr[2]/td/div/table/tbody/tr/td/div/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr[1]/td[7]/div",
    "detalle_btn": "/html/body/table/tbody/tr/td/center/div/form/div[2]/div/table/tbody/tr/td/div/table/tbody/tr[2]/td/div/table/tbody/tr/td/div/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr[2]/td[8]/div/input",
    # hidden input that opens the PDF
    "dni_pdf_btn": "/html/body/table/tbody/tr/td/center/div/form/div[2]/table/tbody/tr/td/div/table/tbody/tr[2]/td/div/table/tbody/tr[9]/td/div/table/tbody/tr/td/div/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr[3]/td[2]/div/input",
}


def build_driver(download_dir: Path, headless: bool = False) -> webdriver.Firefox:
    options = FirefoxOptions()
    if headless:
        options.add_argument("-headless")

    # Configure automatic PDF download
    profile = {
        "browser.download.folderList": 2,  # use custom folder
        "browser.download.dir": str(download_dir),
        "browser.download.useDownloadDir": True,
        "browser.helperApps.neverAsk.saveToDisk": ",".join([
            "application/pdf",
            "application/octet-stream",
        ]),
        # Disable built-in PDF viewer so it downloads instead of opening in tab
        "pdfjs.disabled": True,
        # Avoid download prompt
        "browser.download.manager.showWhenStarting": False,
        "browser.download.manager.focusWhenStarting": False,
        "browser.download.manager.alertOnEXEOpen": False,
        "browser.download.manager.closeWhenDone": True,
        "browser.download.manager.useWindow": False,
        "browser.download.manager.showAlertOnComplete": False,
        "browser.download.panel.shown": False,
    }

    for k, v in profile.items():
        options.set_preference(k, v)

    service = FirefoxService(executable_path=GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    driver.maximize_window()
    return driver


def wait_xpath(driver, xpath: str, timeout: int = 30):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def click_xpath(driver, xpath: str, timeout: int = 30):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
    try:
        el.click()
    except ElementClickInterceptedException:
        # Click via JS as fallback
        driver.execute_script("arguments[0].click();", el)
    return el


def safe_find(driver, xpath: str):
    try:
        return driver.find_element(By.XPATH, xpath)
    except Exception:
        return None


def login(driver, username: str, password: str):
    driver.get(LOGIN_URL)
    user_el = wait_xpath(driver, XPATHS["usuario"], 40)
    pass_el = wait_xpath(driver, XPATHS["password"], 40)
    user_el.clear(); user_el.send_keys(username)
    pass_el.clear(); pass_el.send_keys(password)
    # Try submit via Enter or form submit
    pass_el.submit()


def navigate_to_consulta_operacion(driver):
    # Wait for the workspace to load and click the link
    try:
        click_xpath(driver, XPATHS["consulta_operacion"], 40)
    except TimeoutException:
        # Sometimes the span is not clickable; try clicking parent anchor
        parent_anchor_xpath = XPATHS["consulta_operacion"].rsplit("/span", 1)[0]
        click_xpath(driver, parent_anchor_xpath, 40)


def perform_consulta(driver, dni: str) -> str:
    # Fill DNI and click Consultar
    dni_el = wait_xpath(driver, XPATHS["dni_input"], 40)
    dni_el.clear(); dni_el.send_keys(dni)
    click_xpath(driver, XPATHS["consultar_btn"], 40)

    # Determine if there are results: try to find estado cell
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, XPATHS["estado_cell"])) )
    except TimeoutException:
        return "NO_PEDIDOS"

    # Click estado first (según requerimiento) y luego detalle
    click_xpath(driver, XPATHS["estado_cell"], 20)
    # Click detalle
    click_xpath(driver, XPATHS["detalle_btn"], 30)
    return "OK"


def open_pdf_and_download(driver) -> Optional[Path]:
    # The element is display:none; we can remove style and click via JS
    el = wait_xpath(driver, XPATHS["dni_pdf_btn"], 40)
    driver.execute_script("arguments[0].style.display = 'block'; arguments[0].removeAttribute('hidden');", el)
    driver.execute_script("arguments[0].click();", el)

    # When clicking, a new tab may open or a direct download may start.
    # We'll wait for a file to appear in the download dir.
    # We configured Firefox to auto-download PDFs.
    return None


def wait_for_new_download(download_dir: Path, timeout: int = 60) -> Optional[Path]:
    end = time.time() + timeout
    latest = None
    while time.time() < end:
        pdfs = list(download_dir.glob("*.pdf"))
        if pdfs:
            latest = max(pdfs, key=lambda p: p.stat().st_mtime)
            # Ensure the download is complete (no .part file)
            part = latest.with_suffix(latest.suffix + ".part")
            if not part.exists():
                return latest
        time.sleep(1)
    return latest


def run(username: str, password: str, dni: str, download_dir: Path, headless: bool = False) -> Optional[Path]:
    driver = build_driver(download_dir, headless=headless)
    try:
        login(driver, username, password)
        navigate_to_consulta_operacion(driver)
        status = perform_consulta(driver, dni)
        if status == "NO_PEDIDOS":
            print("NO_PEDIDOS")
            return None
        # Open pdf
        open_pdf_and_download(driver)
        pdf = wait_for_new_download(download_dir, timeout=120)
        if pdf:
            print(str(pdf))
        else:
            print("PDF_NOT_FOUND")
        return pdf
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main(argv=None):
    # Cargar variables desde .env si existe
    load_dotenv()

    parser = argparse.ArgumentParser(description="Automatiza IRIS para consultar y descargar PDF por DNI")
    parser.add_argument("--dni", required=True, help="DNI a consultar")
    parser.add_argument("--username", default="drcartof", help="Usuario de login (default drcartof)")
    parser.add_argument("--password", default=os.getenv("IRIS_PASSWORD", "ITTcuJV1"), help="Password (default incluida)")
    parser.add_argument("--download-dir", default=str(Path.cwd() / "downloads"), help="Carpeta de descarga de PDFs")
    parser.add_argument("--headless", action="store_true", help="Ejecutar Firefox en modo headless")
    args = parser.parse_args(argv)

    # Si no hay password, usar la default hardcodeada; ya la pusimos como default.

    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    run(args.username, args.password, args.dni, download_dir, headless=args.headless)


if __name__ == "__main__":
    main()
