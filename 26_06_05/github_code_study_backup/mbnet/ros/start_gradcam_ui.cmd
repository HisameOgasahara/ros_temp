@echo off
cd /d "%~dp0..\.."
set "PYTHONPATH=%CD%\pytorch-ssd"

echo Starting SSD Grad-CAM UI...
echo Working directory: %CD%
echo PYTHONPATH: %PYTHONPATH%
echo.

set "PYTHON_EXE=python"
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

"%PYTHON_EXE%" -u mbnet\ros\ssd_gradcam_ui.py ^
  --net mb1-ssd ^
  --labels mbnet\ros\labels.txt ^
  --threshold 0.25 ^
  --top-k 10

echo.
echo UI closed.
pause
