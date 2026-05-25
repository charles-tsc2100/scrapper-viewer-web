@echo off
:: ============================================================
::  BOQ Converter — Lark Sync Setup
::  Run this once on each team member's machine.
::  Double-click to run. No Python or coding knowledge needed.
::  Credentials are pre-filled. Just share and run.
:: ============================================================

echo.
echo  BOQ Converter - Lark Sync Setup
echo  ================================
echo.

set "CONFIG_DIR=%APPDATA%\BOQConverter"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

(
echo {
echo   "app_id":         "cli_aa856c2a8eb85ed3",
echo   "app_secret":     "tNiHzzLyAnklx9Wx6SrCFgSCuO4x4FJn",
echo   "base_app_token": "TpUUbD6FNazXHxsP4vylgJVTgR2",
echo   "table_id":       "tbliYZjLsVLVVMmY",
echo   "field_map": {
echo     "name":     "Project",
echo     "category": "Project Type",
echo     "status":   "Status"
echo   },
echo   "brand_usage_table_name": "BOQ Brand Usage"
echo }
) > "%CONFIG_DIR%\lark_config.json"

(
echo {
echo   "url":              "https://xphnzqibeumyxpydrclp.supabase.co",
echo   "anon_key":         "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhwaG56cWliZXVteXhweWRyY2xwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk0MTEzNDksImV4cCI6MjA5NDk4NzM0OX0.F8vDeWNNdkxKHdGZSh9RWpzsNB1sQlIxFSmShwf3f_w",
echo   "service_role_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhwaG56cWliZXVteXhweWRyY2xwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTQxMTM0OSwiZXhwIjoyMDk0OTg3MzQ5fQ.n7Vs4b1538F3a3WXqKVHzausNd6ebf752UxTbrdOSkE"
echo }
) > "%CONFIG_DIR%\db_config.json"

if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Setup failed. Please contact your admin.
    echo.
    pause
    exit /b 1
)

echo   [OK] %CONFIG_DIR%\lark_config.json
echo   [OK] %CONFIG_DIR%\db_config.json
echo.
echo  Setup complete! You can now use the "Refresh from Lark"
echo  button inside the BOQ Converter app.
echo.
pause
