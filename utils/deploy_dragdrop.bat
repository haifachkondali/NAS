@echo off
REM Script de déploiement GNS3 - Mode glisser-déposer (Windows)

if "%~1"=="" (
    echo [Erreur] Veuillez glisser le dossier du projet GNS3 sur ce fichier !
    pause
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "TARGET_DIR=%~1"

echo ============================================
echo Outil de deploiement GNS3
echo ============================================
echo.

cd /d "%SCRIPT_DIR%"
python deploy_dragdrop.py "%TARGET_DIR%"

if %ERRORLEVEL% EQU 0 (
    echo Deploiement termine !
) else (
    echo Echec du deploiement !
)

pause
