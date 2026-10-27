@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Once kurulum.bat dosyasini calistirin.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m streamlit run app.py

