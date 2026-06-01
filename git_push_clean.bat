@echo off
echo ========================================
echo   Git Push dengan .gitignore
echo ========================================
echo.

cd "D:\SEMESTER 4\KDA\batch 2\project-kda-kelompok3"

echo [1/6] Cek status git...
git status
echo.

echo [2/6] Hapus semua file dari git tracking (file tetap ada di lokal)...
git rm -r --cached .
echo.

echo [3/6] Add file sesuai .gitignore...
git add .
echo.

echo [4/6] Cek file yang akan di-commit...
echo File yang akan di-commit:
git status
echo.

echo [5/6] Commit perubahan...
set /p commit_msg="Masukkan commit message (atau tekan Enter untuk default): "
if "%commit_msg%"=="" set commit_msg=Clean repository: apply .gitignore and update structure

git commit -m "%commit_msg%"
echo.

echo [6/6] Push ke GitHub...
echo Pilih branch:
echo 1. main
echo 2. master
set /p branch_choice="Pilih (1/2): "

if "%branch_choice%"=="1" (
    git push origin main
) else (
    git push origin master
)

echo.
echo ========================================
echo   Push Selesai!
echo ========================================
echo.
echo Cek di GitHub untuk memastikan file sudah sesuai.
echo.
pause
