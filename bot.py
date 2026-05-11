"""
╔══════════════════════════════════════════════════════════════╗
║        CELESC BOT v2  —  Extractor de Datos de Protocolo     ║
║        Sitio: conecta.celesc.com.br                          ║
╚══════════════════════════════════════════════════════════════╝

REQUISITOS:
    pip install selenium webdriver-manager

USO:
    python celesc_bot.py

CONFIGURACIÓN:
    Editar la sección CONFIG más abajo.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# ─────────────────────────────────────────────────────────────────
# ██  CONFIG  ██  Editar estos valores antes de ejecutar
# ─────────────────────────────────────────────────────────────────
CONFIG = {
    "email":     "projetos2@reevisa.com.br",      # ← Su correo CELESC
    "password":  "Celesc@0820",              # ← Su contraseña
    "protocolo": "8072121695",                   # ← Número de protocolo

    # ── Opciones del navegador ──────────────────────────────────
    "headless":  False,   # False = ver el navegador / True = en segundo plano
    "timeout":   100,      # Segundos máximos de espera por elemento
}

# ─────────────────────────────────────────────────────────────────
# NOTA PARA IMPLEMENTACIÓN FUTURA (BATCH/LOTE):
#   protocolos = ["111", "222", "333"]
#   for p in protocolos:
#       CONFIG["protocolo"] = p
#       run_bot()
# ─────────────────────────────────────────────────────────────────

URL_INICIO = "https://conecte.celesc.com.br/pagina-inicial/"

# ── XPATHs basados en la estructura HTML Angular real ─────────────
#
# Los botones Angular tienen el texto dentro de un <span> con espacios
# (" Minha Celesc "), por eso usamos normalize-space() en el <span>.
#
XPATH = {
    # <button class="default"><span> Minha Celesc </span></button>
    "minha_celesc": (
        "//button[contains(@class,'default')]"
        "[.//span[contains(normalize-space(.),'Minha Celesc')]]"
    ),
    # <button class="default"><span> Fazer novo cadastro </span></button>
    "fazer_cadastro": (
        "//button[contains(@class,'default')]"
        "[.//span[contains(normalize-space(.),'Fazer novo cadastro')]]"
    ),
    # <button class="default" disabled><span> Entrar </span></button>
    "entrar": (
        "//button[contains(@class,'default')]"
        "[.//span[contains(normalize-space(.),'Entrar')]]"
    ),
    # <button class="small outlined"><span> Selecionar protocolo </span></button>
    "selecionar": (
        "//button[contains(@class,'outlined')]"
        "[.//span[contains(normalize-space(.),'Selecionar protocolo')]]"
    ),
}

# ── CSS Selectors para inputs (estructura Angular exacta) ──────────
CSS = {
    # <input type="email" class="empty no-validate ...">
    "email":     "input[type='email']",
    # <input type="password" class="empty no-validate ...">
    "password":  "input[type='password']",
    # <input type="text" class="... left-icon ...">
    "protocolo": "input[type='text'].left-icon",
}

XPATH.update({
    "servicos_concluidos": "//h2[contains(.,'Serviços concluídos') or contains(.,'Serviços')]",
    "ver_mais": "//button[contains(.,'Ver mais') or contains(.,'ver detalhes')]",
})

CSS.update({
    "card_servicio": "mat-card, .mat-card-content, .servico-item",
})


# ─────────────────────────────────────────────────────────────────
# Helpers de consola
# ─────────────────────────────────────────────────────────────────

def print_banner():
    print("\n" + "═" * 62)
    print("  🤖  CELESC BOT v2  —  Extractor de Datos de Protocolo")
    print("═" * 62)
    print(f"  Protocolo : {CONFIG['protocolo']}")
    print(f"  Email     : {CONFIG['email']}")
    print(f"  Headless  : {CONFIG['headless']}\n")

def step(n, msg):    print(f"\n  [{n}] {msg}")
def ok(msg):         print(f"       ✓ {msg}")
def buscar(msg):     print(f"       ↳ {msg}...")

def print_datos(datos: dict):
    print("\n" + "═" * 62)
    print("  📋  DATOS EXTRAÍDOS DEL PROTOCOLO")
    print("═" * 62)
    if not datos:
        print("  ⚠️  No se encontraron datos en la página.")
    else:
        for clave, valor in datos.items():
            print(f"  • {clave:<35} {valor}")
    print("═" * 62 + "\n")


# ─────────────────────────────────────────────────────────────────
# Setup del driver
# ─────────────────────────────────────────────────────────────────

def crear_driver() -> webdriver.Chrome:
    opts = Options()
    if CONFIG["headless"]:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)
    # Ocultar webdriver para evitar detección de bot
    driver.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    return driver


# ─────────────────────────────────────────────────────────────────
# Acciones del bot
# ─────────────────────────────────────────────────────────────────

def clic_xpath(driver, wait, key: str, desc: str):
    """
    Espera un botón Angular por XPATH y hace click vía JS.
    JS click es más fiable que .click() en apps Angular con overlays.
    """
    buscar(f"Buscando botón '{desc}'")
    elem = wait.until(EC.presence_of_element_located((By.XPATH, XPATH[key])))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    time.sleep(0.6)
    driver.execute_script("arguments[0].click();", elem)
    ok(f"Click en '{desc}'")
    return elem


def clic_entrar(driver, wait):
    """
    El botón 'Entrar' empieza con disabled="".
    Angular lo habilita al detectar valores en email+password.
    Esperamos a que desaparezca el atributo disabled.
    """
    buscar("Esperando que 'Entrar' se habilite (Angular valida campos)")
    xpath = XPATH["entrar"]
    wait.until(lambda d:
        d.find_element(By.XPATH, xpath).get_attribute("disabled") is None
    )
    elem = driver.find_element(By.XPATH, xpath)
    driver.execute_script("arguments[0].click();", elem)
    ok("Click en 'Entrar'")


def llenar_input(driver, wait, css: str, valor: str, desc: str):
    """
    Escribe carácter a carácter para disparar los eventos de Angular
    (ngModel / reactive forms necesitan input events reales).
    """
    buscar(f"Buscando input '{desc}'")
    elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    driver.execute_script("arguments[0].click();", elem)
    time.sleep(0.3)
    elem.clear()
    for char in valor:
        elem.send_keys(char)
        time.sleep(0.04)
    ok(f"'{desc}' rellenado")
    return elem


# ─────────────────────────────────────────────────────────────────
# Extracción de datos
# ─────────────────────────────────────────────────────────────────

def extraer_datos_body(driver) -> dict:
    """Extracción mejorada y más agresiva para CELESC (Angular)"""
    datos = {}
    
    # Esperar un poco más para que Angular renderice todo
    time.sleep(3)
    
    # === 1. Texto completo del body (método más confiable) ===
    body_text = driver.find_element(By.TAG_NAME, "body").text
    lineas = [line.strip() for line in body_text.splitlines() if line.strip()]

    current_section = ""
    for linea in lineas:
        # Detectar secciones principales
        if any(seccion in linea for seccion in ["Dados do protocolo", "Dados do cliente", 
                                               "Serviços concluídos", "Serviço", "Projeto de"]):
            current_section = linea
            if current_section not in datos:
                datos[current_section] = ""
            continue

        if current_section and linea:
            if datos[current_section]:
                datos[current_section] += "\n" + linea
            else:
                datos[current_section] = linea

    # === 2. Extracción por pares (Label : Valor) ===
    for i in range(len(lineas) - 1):
        lin1 = lineas[i]
        lin2 = lineas[i+1]
        if len(lin1) < 60 and len(lin2) > 5 and not any(x in lin1 for x in ["Serviço", "Projeto", "Linha"]):
            clave = lin1.replace(":", "").strip()
            if clave and clave not in datos:
                datos[clave] = lin2

    # === 3. Capturar tarjetas de servicios con más detalle ===
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, "mat-card, .mat-card, .card, div[class*='servico'], div[role='region']")
        servicios_text = []
        for card in cards:
            txt = card.text.strip()
            if txt and ("Serviço" in txt or "Projeto" in txt or "Análise" in txt or "liberada" in txt.lower()):
                servicios_text.append(txt)
        
        if servicios_text:
            datos["SERVIÇOS_DETALLADOS"] = "\n\n" + "="*50 + "\n\n".join(servicios_text)
    except:
        pass

    # === 4. Buscar fechas y estados ===
    try:
        fechas = driver.find_elements(By.XPATH, "//*[contains(text(),'/20') or contains(text(),'/202')]")
        for f in fechas[:15]:
            txt = f.text.strip()
            if len(txt) > 8 and any(x in txt for x in ["liberada", "Envi", "Análise", "Projeto"]):
                parent = f.find_element(By.XPATH, "./ancestor::div[1]")
                datos[f"Evento_{len(datos)}"] = parent.text.strip()
    except:
        pass

    return datos

# ─────────────────────────────────────────────────────────────────
# Flujo principal
# ─────────────────────────────────────────────────────────────────

def run_bot():
    print_banner()
    driver = crear_driver()
    wait = WebDriverWait(driver, 40)
    
    try:
        step(1, "Abriendo CELESC...")
        driver.get(URL_INICIO)
        time.sleep(6)

        step(2, "Click en 'Minha Celesc' (1ª)")
        clic_xpath(driver, wait, "minha_celesc", "Minha Celesc")
        time.sleep(5)

        step(3, "Click en 'Fazer novo cadastro'")
        clic_xpath(driver, wait, "fazer_cadastro", "Fazer novo cadastro")
        time.sleep(5)

        step(4, "Click en 'Minha Celesc' (2ª)")
        clic_xpath(driver, wait, "minha_celesc", "Minha Celesc")
        time.sleep(5)

        step(5, "Rellenando credenciales...")
        llenar_input(driver, wait, CSS["email"], CONFIG["email"], "email")
        time.sleep(2)
        llenar_input(driver, wait, CSS["password"], CONFIG["password"], "senha")
        time.sleep(3)

        step(6, "Click en 'Entrar'")
        clic_entrar(driver, wait)
        time.sleep(8)

        step(7, f"Ingresando protocolo {CONFIG['protocolo']}")
        llenar_input(driver, wait, CSS["protocolo"], CONFIG["protocolo"], "protocolo")
        time.sleep(4)

        step(8, "Click en 'Selecionar protocolo'")
        clic_xpath(driver, wait, "selecionar", "Selecionar protocolo")
        time.sleep(10)        # Tiempo importante

        # Intentar cambiar a pestaña de servicios/histórico si existe
        step(9, "Buscando pestañas de Serviços / Histórico...")
        try:
            tabs = driver.find_elements(By.XPATH, 
                "//mat-tab-header//div[contains(.,'Serviços') or contains(.,'Histórico') or contains(.,'Detalhes')]")
            for tab in tabs:
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(3)
        except:
            pass

        # Expandir todo
        step(10, "Expandiendo secciones...")
        try:
            for btn in driver.find_elements(By.XPATH, "//button[contains(.,'Ver mais') or contains(.,'ver detalhes') or contains(.,'Expandir')]"):
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2.5)
        except:
            pass

        driver.save_screenshot(f"protocolo_{CONFIG['protocolo']}_final.png")
        ok("Screenshot guardado")

        step(11, "Extrayendo datos completos...")
        datos = extraer_datos_body(driver)
        print_datos(datos)

    except Exception as e:
        print(f"\n ❌ ERROR: {e}")
        print(f" URL: {driver.current_url}")
        driver.save_screenshot(f"ERROR_{CONFIG['protocolo']}.png")
    finally:
        input("\nPresiona ENTER para cerrar el navegador...")
        driver.quit()
        
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_bot()
