@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Cai dat PoseFit trong moi truong rieng. Can Python 3.11 va ket noi mang.
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv ".venv"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -B launch.py --qt-provider installed --preflight-only
if errorlevel 1 goto failed
echo Da cai dat va kiem tra. Dong cua so nay, nhap doi Mo_PoseFit.vbs de mo giao dien.
pause
exit /b 0
:failed
echo Chua cai dat thanh cong. Hay gui thong bao loi cho truong nhom. Khong sua manifest hoac doi model.
pause
exit /b 1
