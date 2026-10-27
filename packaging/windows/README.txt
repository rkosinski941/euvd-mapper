EUVD-mapper per-user package
Git pin: dbd9036611e525bcb1abeb8fe8f97ba31dfd487a
Sandbox patch: see PATCH.txt. Inserted sheets use numeric rIds so Excel can open them.
Package: euvd-mapper 0.2.0
openpyxl pin: 3.1.5
tzdata pin: 2026.5 (Windows zoneinfo data for America/New_York)

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
