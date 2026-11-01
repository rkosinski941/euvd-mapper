EUVD-mapper per-user package
Git pin: dbd9036611e525bcb1abeb8fe8f97ba31dfd487a
Sandbox patch: see PATCH.txt. Inserted sheets use numeric rIds so Excel can open them.
Package: euvd-mapper 0.2.0
openpyxl pin: 3.1.5
et-xmlfile pin: 2.0.0
tzdata pin: 2026.5 (Windows zoneinfo data for America/New_York)
pip pin: 26.2.2
setuptools pin: 84.2.1
wheel pin: 0.48.0
packaging pin: 26.3 (dependency of wheel)
Wheel hashes: wheel-pins.txt. Every pin is a py3-none-any or py2.py3-none-any wheel that installs on cp313 win_amd64.
CPython embed pin: 3.13.17 (Windows embeddable package, 64-bit)
URL: https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip
SHA-256: 9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38
Python 3.13.18 (2026-10-25) is source-only. 3.13.17 is the newest 3.13 release with an official embeddable amd64 zip.
Install rewrites python313._pth so it keeps python313.zip, adds Lib\site-packages, and enables import site.

This folder is the installer. It does not need administrator rights.
The default install root is %LOCALAPPDATA%\EUVD-mapper.
The default Start menu folder is %APPDATA%\Microsoft\Windows\Start Menu\Programs.
Nothing is written to Program Files or HKLM.

Do not run the default install until Rich approves it.
A sandbox test passes -InstallRoot and -StartMenu explicitly.

Install, from this folder:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1

Sandbox example:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -InstallRoot C:\path\EUVD-mapper -StartMenu C:\path\StartMenu

Force the bundled Python instead of a venv:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ForceEmbed

Uninstall only what this installer added:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1 -InstallRoot C:\path\EUVD-mapper

Drop a report on bin\euvd-enrich.cmd after install.
The window stays open. The copy is written next to the report as name-EUVD.xlsx.
The input file is not overwritten.
Cache files live in the install root under cache and are kept across upgrades.
Uninstall removes that cache because it lives inside the install root.
It also removes __pycache__ folders under the install root.
It does not remove an enriched workbook that sits next to a report.
