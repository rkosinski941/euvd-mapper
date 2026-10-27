@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%ROOT%\python\python.exe"
if not exist "%PY%" (
  echo EUVD-mapper Python was not found.
  exit /b 1
)
set "HAS_CACHE=0"
for %%A in (%*) do (
  if /I "%%~A"=="--cache-dir" set "HAS_CACHE=1"
)
if "%HAS_CACHE%"=="0" (
  "%PY%" -m euvd_mapper %* --cache-dir "%ROOT%\cache"
) else (
  "%PY%" -m euvd_mapper %*
)
exit /b %ERRORLEVEL%
