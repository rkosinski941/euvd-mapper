@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%ROOT%\python\python.exe"
if not exist "%PY%" (
  echo EUVD-mapper Python was not found.
  echo Expected %ROOT%\venv\Scripts\python.exe
  pause
  exit /b 1
)
if "%~1"=="" goto usage
set "IN=%~f1"
set "OUT=%~dpn1-EUVD.xlsx"
echo Enriching "%IN%"
echo Output "%OUT%"
"%PY%" -m euvd_mapper enrich-xlsx "%IN%" -o "%OUT%" --cache-dir "%ROOT%\cache"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Enrich failed with exit code %RC%.
pause
exit /b %RC%
:usage
echo Drop a Black Duck project report .xlsx onto this file.
echo The copy is written next to the report as name-EUVD.xlsx.
pause
exit /b 1
