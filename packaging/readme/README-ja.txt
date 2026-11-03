VARIANS {version} — すぐに使える版

このアーカイブには、Varians と、その動作に必要なもの（Python、Qt、lxml、
Saxon）がすべて含まれています。ほかに何もインストールする必要はありません。


インストールと起動
------------------
Windows（10 または 11、64 ビット）
  1. アーカイブ全体を展開します（右クリック →「すべて展開…」）。展開先は
     たとえば「ドキュメント」です。zip ファイルの中から直接 Varians を起動
     しないでください。
  2. Varians-{version} フォルダーの Varians.exe をダブルクリックします。
  3. 初回起動：Varians には署名がないため、Windows が「Windows によって PC
     が保護されました」と表示することがあります。「詳細情報」をクリック
     し、「実行」をクリックしてください。ウイルス対策ソフトが起動前に
     プログラムを検査することもあります。
  デスクトップにショートカットを作るには：Varians.exe を右クリック →
  「送る」→「デスクトップ (ショートカットを作成)」（Windows 11 では先に
  「その他のオプションを確認」）。

macOS（Apple シリコン搭載の Mac（M1、M2…）には「macos-arm64」、Intel 搭載
の Mac には「macos-x64」のアーカイブ）
  1. アーカイブをダブルクリックし、Varians.app を「アプリケーション」
     フォルダーにドラッグします。
  2. 初回起動：Varians は Apple の署名を受けていないため、macOS は開くこと
     を拒否します（「Apple は検証できませんでした…」）。メッセージを閉じ、
     「システム設定」→「プライバシーとセキュリティ」を開いて、下のほうの
     Varians についてのメッセージの横にある「このまま開く」をクリックし、
     確認します。macOS 14 以前では、Varians.app を右クリック（または
     control キーを押しながらクリック）→「開く」→「開く」でも構いません。
     確認は最初の 1 回だけです。
  macOS が Varians は「壊れている」と表示する場合は、ターミナルで次を入力
  します：
     xattr -dr com.apple.quarantine /Applications/Varians.app

Linux（64 ビット x86。Ubuntu 22.04、Debian 12、Fedora 36 以降）
  1. アーカイブを展開：  unzip Varians-{version}-linux-x64.zip
  2. 起動：              ./Varians-{version}/Varians
  Varians は、どの Linux デスクトップにもあるグラフィックス・ライブラリ
  （OpenGL、libxcb、fontconfig）を使います。足りないものがあれば、たとえば
  Debian や Ubuntu では：
     sudo apt install libegl1 libgl1 libxcb1 libxkbcommon0 libfontconfig1


更新
----
リリースのページから新しいアーカイブをダウンロードし、
  https://github.com/MarjorieBurghart/Varians/releases
古いフォルダー（または Varians.app）を新しいものと置き換えます。プロジェクト
と設定はこのフォルダーの中にはないので、そのまま残ります。

Varians をアンインストールするには、このフォルダー（または Varians.app）を
削除するだけです。


確認
----
アーカイブ：各アーカイブには SHA-256 のハッシュ値があります（リリースの
ページの .sha256 ファイル）。計算するには：
  Windows（PowerShell）：  Get-FileHash Varians-{version}-windows-x64.zip
  macOS：                  shasum -a 256 Varians-{version}-macos-arm64.zip
  Linux：                  sha256sum Varians-{version}-linux-x64.zip

インストール：問題があるときは、Varians が自分の翻訳、リソース、検証、変換
（lxml と Saxon）、ウィンドウを自分で確認し、報告を書き出せます（約 1 分）：
  Windows（コマンド プロンプトで、Varians のフォルダーにて）：
     start /wait Varians.exe --self-test report.json
  macOS：
     /Applications/Varians.app/Contents/MacOS/Varians --self-test ~/report.json
  Linux：
     ./Varians --self-test report.json
この報告を問題の報告に添付してください：
  https://github.com/MarjorieBurghart/Varians/issues


ヘルプ
------
使い方は Varians の中にあります：ヘルプ → Variansヘルプ (F1)。
インターフェースの言語で表示されます（表示 → 言語）。


構成要素
--------
Varians には次のものが含まれます：Python（PSF ライセンス）、Qt と PySide6
（LGPL v3。差し替え可能な独立したライブラリ。ソースは https://code.qt.io）、
lxml、libxml2、libxslt（BSD、MIT）、Saxon HE（saxonche、MPL 2.0）、
certifi（MPL 2.0）、TEI Stylesheets（CC BY-SA 3.0 または BSD）、SchXslt2
（MIT）。これらのライセンスの本文は licences フォルダーにあります。
