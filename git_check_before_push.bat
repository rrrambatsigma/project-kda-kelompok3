@echo off
echo ========================================
echo   Cek File Sebelum Push
echo ========================================
echo.

cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3"

echo [INFO] File yang akan di-track oleh git:
echo.
git ls-files
echo.

echo ========================================
echo   File yang DI-IGNORE (tidak akan di-push):
echo ========================================
echo.

echo Cek manual file berikut TIDAK boleh muncul di list di atas:
echo   - __pycache__/
echo   - hasil/models/*.pkl
echo   - hasil/hasil_prediksi_drift.csv
echo   - autogenerate/.keys/
echo   - autogenerate/smart_grid_data_v2.csv
echo   - *.pyc
echo.

echo ========================================
echo   File yang HARUS ADA di list di atas:
echo ========================================
echo   - .gitignore
echo   - dashboard.py
echo   - requirements.txt
echo   - README.md
echo   - autogenerate/ML.py
echo   - autogenerate/encrypt.py
echo   - data/df_train.csv
echo.

pause
