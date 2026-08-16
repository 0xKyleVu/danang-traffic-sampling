@echo off
REM Wrapper cho Windows Task Scheduler goi moi 30 phut.
REM Ghi log ra run_log.txt de kiem tra khi chay nen.
cd /d "%~dp0"
echo. >> run_log.txt
echo ===== %date% %time% ===== >> run_log.txt
python collect_traffic.py >> run_log.txt 2>&1
