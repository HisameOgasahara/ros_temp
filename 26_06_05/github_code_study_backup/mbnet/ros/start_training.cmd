@echo off
cd /d "%~dp0..\.."
set "PYTHONPATH=%CD%\pytorch-ssd"

set "PYTHON_EXE=python"
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

set "DATASET_DIR=%~1"
if "%DATASET_DIR%"=="" set "DATASET_DIR=mbnet\ros\data_voc"

set "PRETRAINED_MODEL=%~2"
if "%PRETRAINED_MODEL%"=="" set "PRETRAINED_MODEL=models\mobilenet-v1-ssd-mp-0_675.pth"

"%PYTHON_EXE%" mbnet\ros\train_ssd.py ^
  --dataset-type voc ^
  --datasets "%DATASET_DIR%" ^
  --net mb1-ssd ^
  --resolution 300 ^
  --batch-size 16 ^
  --num-workers 0 ^
  --num-epochs 50 ^
  --lr 0.005 ^
  --base-net-lr 0.0005 ^
  --pretrained-ssd "%PRETRAINED_MODEL%" ^
  --checkpoint-folder mbnet\ros\models

echo.
echo Training finished or stopped.
pause
