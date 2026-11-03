VARIANS {version} — ГОТОВАЯ К ИСПОЛЬЗОВАНИЮ ВЕРСИЯ

Этот архив содержит Varians и всё, что ему нужно (Python, Qt, lxml,
Saxon): больше ничего устанавливать не требуется.


УСТАНОВКА И ЗАПУСК
------------------
Windows (10 или 11, 64 бита)
  1. Распакуйте весь архив (правая кнопка → «Извлечь все…»), например в
     папку «Документы». Не запускайте Varians прямо из zip-архива.
  2. Дважды щёлкните Varians.exe в папке Varians-{version}.
  3. Первый запуск: Varians не подписан, поэтому Windows может показать
     «Система Windows защитила ваш компьютер». Нажмите «Подробнее», затем
     «Выполнить в любом случае». Антивирус тоже может проверить программу
     перед запуском.
  Ярлык на рабочем столе: правая кнопка на Varians.exe → «Отправить» →
  «Рабочий стол (создать ярлык)» (в Windows 11 сначала «Показать
  дополнительные параметры»).

macOS (архив «macos-arm64» для Mac с Apple Silicon: M1, M2…, «macos-x64»
для Mac с процессором Intel)
  1. Дважды щёлкните архив и перетащите Varians.app в папку «Программы».
  2. Первый запуск: Varians не подписан Apple, поэтому macOS отказывается
     его открыть («Apple не может проверить…»). Закройте сообщение и
     откройте «Системные настройки» → «Конфиденциальность и безопасность»:
     внизу, рядом с сообщением о Varians, нажмите «Всё равно открыть» и
     подтвердите. В macOS 14 и более ранних достаточно щёлкнуть Varians.app
     правой кнопкой (или с нажатой клавишей Control) → «Открыть» →
     «Открыть». macOS спрашивает только один раз.
  Если macOS сообщает, что Varians «повреждён», введите в Терминале:
     xattr -dr com.apple.quarantine /Applications/Varians.app

Linux (64 бита x86; Ubuntu 22.04, Debian 12, Fedora 36 или новее)
  1. Распакуйте архив:  unzip Varians-{version}-linux-x64.zip
  2. Запустите:         ./Varians-{version}/Varians
  Varians использует графические библиотеки, которые есть на любом
  рабочем столе Linux (OpenGL, libxcb, fontconfig). Если какой-то не
  хватает, например в Debian или Ubuntu:
     sudo apt install libegl1 libgl1 libxcb1 libxkbcommon0 libfontconfig1


ОБНОВЛЕНИЕ
----------
Скачайте новый архив со страницы версий,
  https://github.com/MarjorieBurghart/Varians/releases
и замените старую папку (или Varians.app) новой. Ваши проекты и настройки
находятся не в этой папке: они сохранятся.

Чтобы удалить Varians, просто удалите эту папку (или Varians.app).


ПРОВЕРКА
--------
Архив: у каждого архива есть контрольная сумма SHA-256 (файл .sha256 на
странице версий). Чтобы вычислить её:
  Windows (PowerShell):  Get-FileHash Varians-{version}-windows-x64.zip
  macOS:                 shasum -a 256 Varians-{version}-macos-arm64.zip
  Linux:                 sha256sum Varians-{version}-linux-x64.zip

Установка: при неполадках Varians может сам проверить свои переводы,
ресурсы, валидацию, преобразования (lxml и Saxon) и своё окно и записать
отчёт (около минуты):
  Windows (командная строка, в папке Varians):
     start /wait Varians.exe --self-test otchet.json
  macOS:
     /Applications/Varians.app/Contents/MacOS/Varians --self-test ~/otchet.json
  Linux:
     ./Varians --self-test otchet.json
Приложите этот отчёт к сообщению о проблеме:
  https://github.com/MarjorieBurghart/Varians/issues


СПРАВКА
-------
Руководство находится в самой программе: Справка → Справка Varians (F1), на
языке интерфейса (Вид → Язык).


КОМПОНЕНТЫ
----------
В составе Varians: Python (лицензия PSF); Qt и PySide6 (LGPL v3: отдельные
заменяемые библиотеки; исходный код на https://code.qt.io); lxml, libxml2 и
libxslt (BSD, MIT); Saxon HE (saxonche, MPL 2.0); certifi (MPL 2.0); TEI
Stylesheets (CC BY-SA 3.0 или BSD); SchXslt2 (MIT). Тексты этих лицензий
находятся в папке licences.
