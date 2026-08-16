@echo off
REM ============================================================
REM  EDS Spectrum Simulator - Windows デスクトップ版ビルド
REM  リポジトリのルートで実行してください:  desktop\build_windows.bat
REM  出力: dist\EDS-Simulator\EDS-Simulator.exe
REM ============================================================
python -m pip install --upgrade pip || goto :err
pip install -r requirements.txt pyinstaller pywebview || goto :err
pyinstaller --noconfirm --clean desktop\eds_sim_app.spec || goto :err
echo.
echo [OK] dist\EDS-Simulator\EDS-Simulator.exe が生成されました。
echo      フォルダごと配布してください（.exe 単体では動きません）。
goto :eof
:err
echo [ERROR] ビルドに失敗しました。上のログを確認してください。
exit /b 1
