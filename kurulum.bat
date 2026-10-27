@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto hata
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
echo.
echo Kurulum tamamlandi. Artik baslat.bat dosyasini calistirabilirsiniz.
pause
exit /b 0

:hata
echo Python 3 bulunamadi. Once Python 3.11 veya daha yeni bir surum kurun.
pause
exit /b 1

