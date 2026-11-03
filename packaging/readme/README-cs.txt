VARIANS {version} — VERZE PŘIPRAVENÁ K POUŽITÍ

Tento archiv obsahuje Varians a vše, co potřebuje (Python, Qt, lxml,
Saxon): nic dalšího není třeba instalovat.


INSTALACE A SPUŠTĚNÍ
--------------------
Windows (10 nebo 11, 64 bitů)
  1. Rozbalte celý archiv (pravé tlačítko → „Extrahovat vše…“), například do
     složky Dokumenty. Nespouštějte Varians přímo z archivu zip.
  2. Poklepejte na Varians.exe ve složce Varians-{version}.
  3. První spuštění: Varians není podepsaný, a Windows proto může zobrazit
     „Systém Windows ochránil váš počítač“. Klikněte na „Další informace“ a
     potom na „Přesto spustit“. Program může před spuštěním prověřit také
     antivirus.
  Zástupce na ploše: pravé tlačítko na Varians.exe → „Odeslat“ → „Plocha
  (vytvořit zástupce)“ (ve Windows 11 nejprve „Zobrazit další možnosti“).

macOS (archiv „macos-arm64“ pro Macy s čipem Apple Silicon: M1, M2…,
„macos-x64“ pro Macy s procesorem Intel)
  1. Poklepejte na archiv a přetáhněte Varians.app do složky Aplikace.
  2. První spuštění: Varians není podepsaný společností Apple, a macOS ho
     proto odmítne otevřít („Apple nemůže ověřit…“). Zavřete zprávu a
     otevřete Nastavení systému → Soukromí a zabezpečení: dole, vedle zprávy
     o Varians, klikněte na „Přesto otevřít“ a potvrďte. V macOS 14 nebo
     starším stačí kliknout pravým tlačítkem (nebo s klávesou Ctrl) na
     Varians.app → Otevřít → Otevřít. macOS se zeptá jen jednou.
  Pokud macOS hlásí, že je Varians „poškozený“, zadejte v Terminálu:
     xattr -dr com.apple.quarantine /Applications/Varians.app

Linux (64 bitů x86; Ubuntu 22.04, Debian 12, Fedora 36 nebo novější)
  1. Rozbalte archiv:  unzip Varians-{version}-linux-x64.zip
  2. Spusťte:          ./Varians-{version}/Varians
  Varians používá grafické knihovny, které jsou na každém linuxovém
  desktopu (OpenGL, libxcb, fontconfig). Pokud některá chybí, například v
  Debianu nebo Ubuntu:
     sudo apt install libegl1 libgl1 libxcb1 libxkbcommon0 libfontconfig1


AKTUALIZACE
-----------
Stáhněte nový archiv ze stránky verzí,
  https://github.com/MarjorieBurghart/Varians/releases
a nahraďte starou složku (nebo Varians.app) novou. Vaše projekty a
nastavení nejsou v této složce: zůstanou zachovány.

Chcete-li Varians odinstalovat, stačí smazat tuto složku (nebo Varians.app).


KONTROLA
--------
Archiv: každý archiv má svůj otisk SHA-256 (soubor .sha256 na stránce
verzí). Výpočet:
  Windows (PowerShell):  Get-FileHash Varians-{version}-windows-x64.zip
  macOS:                 shasum -a 256 Varians-{version}-macos-arm64.zip
  Linux:                 sha256sum Varians-{version}-linux-x64.zip

Instalace: při potížích může Varians sám zkontrolovat své překlady, zdroje,
validaci, transformace (lxml a Saxon) a své okno a zapsat o tom zprávu
(asi minutu):
  Windows (příkazový řádek, ve složce Varians):
     start /wait Varians.exe --self-test zprava.json
  macOS:
     /Applications/Varians.app/Contents/MacOS/Varians --self-test ~/zprava.json
  Linux:
     ./Varians --self-test zprava.json
Připojte tuto zprávu k hlášení problému:
  https://github.com/MarjorieBurghart/Varians/issues


NÁPOVĚDA
--------
Návod je přímo ve Varians: Nápověda → Nápověda k Varians (F1), v jazyce
rozhraní (Zobrazení → Jazyk).


SOUČÁSTI
--------
Varians obsahuje: Python (licence PSF); Qt a PySide6 (LGPL v3: samostatné,
nahraditelné knihovny; zdrojové kódy na https://code.qt.io); lxml, libxml2
a libxslt (BSD, MIT); Saxon HE (saxonche, MPL 2.0); certifi (MPL 2.0); TEI
Stylesheets (CC BY-SA 3.0 nebo BSD); SchXslt2 (MIT). Texty těchto licencí
jsou ve složce licences.
