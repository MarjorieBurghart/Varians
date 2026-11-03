VARIANS {version} — READY-TO-USE VERSION

This archive contains Varians and everything it needs (Python, Qt, lxml,
Saxon): there is nothing else to install.


INSTALL AND START
-----------------
Windows (10 or 11, 64-bit)
  1. Extract the whole archive (right-click → "Extract All…"), for example
     into Documents. Do not start Varians from inside the zip file.
  2. Double-click Varians.exe, in the Varians-{version} folder.
  3. First start: since Varians is not signed, Windows may display "Windows
     protected your PC". Click "More info", then "Run anyway". An antivirus
     program may also scan the program before letting it start.
  For a desktop shortcut: right-click Varians.exe → "Send to" → "Desktop
  (create shortcut)" (on Windows 11, first "Show more options").

macOS ("macos-arm64" archive for Apple Silicon Macs: M1, M2…, "macos-x64"
for Intel Macs)
  1. Double-click the archive, then drag Varians.app into the Applications
     folder.
  2. First start: since Varians is not signed by Apple, macOS refuses to
     open it ("Apple could not verify…"). Close the message, then open
     System Settings → Privacy & Security: at the bottom, next to the
     message about Varians, click "Open Anyway" and confirm. On macOS 14 or
     earlier, you can simply right-click (or Control-click) Varians.app →
     Open → Open. macOS asks only once.
  If macOS says that Varians "is damaged", type in the Terminal:
     xattr -dr com.apple.quarantine /Applications/Varians.app

Linux (64-bit x86; Ubuntu 22.04, Debian 12, Fedora 36 or later)
  1. Extract the archive:  unzip Varians-{version}-linux-x64.zip
  2. Start:                ./Varians-{version}/Varians
  Varians uses the graphics libraries found on every Linux desktop (OpenGL,
  libxcb, fontconfig). If one is missing, for example on Debian or Ubuntu:
     sudo apt install libegl1 libgl1 libxcb1 libxkbcommon0 libfontconfig1


UPDATE
------
Download the new archive from the releases page,
  https://github.com/MarjorieBurghart/Varians/releases
then replace the old folder (or Varians.app) with the new one. Your projects
and your settings are not in this folder: they are kept.

To uninstall Varians, simply delete this folder (or Varians.app).


CHECK
-----
The archive: each archive has its SHA-256 checksum (.sha256 file on the
releases page). To compute it:
  Windows (PowerShell):  Get-FileHash Varians-{version}-windows-x64.zip
  macOS:                 shasum -a 256 Varians-{version}-macos-arm64.zip
  Linux:                 sha256sum Varians-{version}-linux-x64.zip

The installation: if something goes wrong, Varians can check its own
translations, resources, validation, transformations (lxml and Saxon) and
window, and write a report (about one minute):
  Windows (command prompt, in the Varians folder):
     start /wait Varians.exe --self-test report.json
  macOS:
     /Applications/Varians.app/Contents/MacOS/Varians --self-test ~/report.json
  Linux:
     ./Varians --self-test report.json
Attach this report to your issue:
  https://github.com/MarjorieBurghart/Varians/issues


HELP
----
The manual is inside Varians: Help → Software Help (F1), in the language of
the interface (View → Language).


COMPONENTS
----------
Varians comes with: Python (PSF license); Qt and PySide6 (LGPL v3: separate
libraries, which can be replaced; sources at https://code.qt.io); lxml, libxml2 and libxslt (BSD, MIT); Saxon HE
(saxonche, MPL 2.0); certifi (MPL 2.0); the TEI Stylesheets (CC BY-SA 3.0 or
BSD); SchXslt2 (MIT). The texts of these licenses are in the licences folder.
