# Automatización IRIS (Firefox + Selenium)

Script en Python que abre Firefox, inicia sesión en IRIS, navega a "Consulta de operación", busca por DNI y, si hay pedidos, entra al detalle y descarga el PDF. Si no hay pedidos, imprime `NO_PEDIDOS`.

## Requisitos
- Windows con PowerShell
- Python 3.9+ instalado en PATH

## Instalación
1. Crear y activar un entorno virtual (opcional recomendado)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

## Configurar credenciales
- Usuario por defecto: `drcartof`
- Password por defecto: incluida en el script (puedes sobreescribir con `--password` o `IRIS_PASSWORD`).

## Ejecutar

```powershell
python -m src.automation --dni 12345678
```

Opciones útiles:
- `--download-dir C:\\ruta\\a\\descargas` (por defecto `./downloads`)
- `--headless` (ejecuta sin UI)
- `--username otro_usuario`

Salida:
- Si no hay pedidos: imprime `NO_PEDIDOS`
- Si descarga PDF: imprime la ruta local del PDF

## Notas técnicas
- Se usa GeckoDriverManager para bajar el geckodriver automáticamente.
- Firefox está configurado para descargar PDF sin preguntar (desactiva visor PDF interno).
- Algunos elementos tienen `display:none`; el script los hace visibles y ejecuta click via JavaScript.

## Troubleshooting
- Si ves error de import `webdriver_manager` o `dotenv`, asegúrate de haber corrido `pip install -r requirements.txt` dentro del entorno virtual.
- Si los XPaths cambian en la página, avísame para ajustarlos a selectores más robustos.
- Si tu red requiere proxy, configura variables de entorno `HTTP_PROXY`/`HTTPS_PROXY`.
