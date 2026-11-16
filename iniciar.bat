@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto preparado
python --version >nul 2>&1
if errorlevel 1 goto sin_python
echo Preparando entorno local. La primera ejecucion requiere internet.
python -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto dependencias
:preparado
".venv\Scripts\python.exe" -c "import django, reportlab, PIL, cryptography, tzdata" >nul 2>&1
if errorlevel 1 goto dependencias
".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 goto error
".venv\Scripts\python.exe" manage.py seed_demo
if errorlevel 1 goto error
echo.
echo Abre http://127.0.0.1:8000 en tu navegador.
echo Usuarios: gerencia / conductor / cliente. Clave: Austral2026!
echo Usa Ctrl+C para detener el servidor.
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
if errorlevel 1 goto error
goto end
:sin_python
echo Instala Python 3.12 o posterior y activa la opcion Add Python to PATH.
pause
goto end
:dependencias
echo Instalando o completando dependencias del entorno local...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
".venv\Scripts\python.exe" -c "import django, reportlab, PIL, cryptography, tzdata" >nul 2>&1
if errorlevel 1 goto error
goto preparado
:error
echo Revisa Python y las dependencias indicadas en README.md.
pause
:end
