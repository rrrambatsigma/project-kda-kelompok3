@echo off
echo ========================================
echo   Git Clean Restart
echo   Hapus Semua di GitHub dan Push Ulang
echo ========================================
echo.
echo PERINGATAN: Script ini akan:
echo 1. Hapus SEMUA file dari GitHub
echo 2. Push ulang hanya file yang diperlukan (sesuai .gitignore)
echo.
echo File di komputer Anda TETAP AMAN, tidak akan terhapus.
echo.
set /p confirm="Lanjutkan? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Dibatalkan.
    pause
    exit
)

cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3"

echo.
echo ========================================
echo [1/9] Cek status awal...
echo ========================================
git status
echo.
pause

echo.
echo ========================================
echo [2/9] Hapus semua file dari git tracking...
echo ========================================
git rm -rf .
echo.

echo.
echo ========================================
echo [3/9] Commit penghapusan...
echo ========================================
git commit -m "Remove all files for clean restart"
echo.

echo.
echo ========================================
echo [4/9] Push penghapusan ke GitHub...
echo ========================================
echo Pilih branch:
echo 1. main
echo 2. master
set /p branch_choice="Pilih (1/2): "

if "%branch_choice%"=="1" (
    set branch=main
) else (
    set branch=master
)

git push origin %branch%
echo.
echo GitHub sekarang sudah kosong!
pause

echo.
echo ========================================
echo [5/9] Add file baru sesuai .gitignore...
echo ========================================
git add .
echo.

echo.
echo ========================================
echo [6/9] Cek file yang akan di-push...
echo ========================================
echo.
echo File yang AKAN di-push:
git status
echo.
echo File yang TIDAK BOLEH muncul di atas:
echo   - __pycache__/
echo   - hasil/models/*.pkl
echo   - hasil/hasil_prediksi_drift.csv
echo   - autogenerate/.keys/
echo   - autogenerate/smart_grid_data_v2.csv
echo.
echo File yang HARUS muncul di atas:
echo   - .gitignore
echo   - dashboard.py
echo   - requirements.txt
echo   - README.md
echo   - autogenerate/ML.py
echo   - autogenerate/encrypt.py
echo.
set /p continue="Apakah file sudah benar? Lanjutkan? (Y/N): "
if /i not "%continue%"=="Y" (
    echo Dibatalkan. Silakan cek .gitignore dan coba lagi.
    pause
    exit
)

echo.
echo ========================================
echo [7/9] Commit file baru...
echo ========================================
git commit -m "Initial commit with clean structure and .gitignore"
echo.

echo.
echo ========================================
echo [8/9] Push ke GitHub...
echo ========================================
git push origin %branch%
echo.

echo.
echo ========================================
echo [9/9] Selesai!
echo ========================================
echo.
echo Push berhasil! Silakan cek GitHub Anda.
echo.
echo Langkah selanjutnya:
echo 1. Buka GitHub repository Anda di browser
echo 2. Pastikan hanya file yang diperlukan yang ada
echo 3. Pastikan tidak ada __pycache__, .pkl, .keys, dll
echo.
pause
