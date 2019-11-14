@echo off
set root=C:%HOMEPATH%\AppData\Local\Continuum\miniconda3
call %root%\Scripts\activate.bat %root%
call conda activate measure
cd "C:%HOMEPATH%\Documents\GitHub\measurement-automation-tools\analog-voltage-control\"
python analogVoltageController.py