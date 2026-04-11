@echo off
chcp 65001 >nul
echo Cleaning up MT5 EA build files...

if exist "Main\SanqingEA.ex5" (
    del /f /q "Main\SanqingEA.ex5"
    echo Deleted: Main\SanqingEA.ex5
)

if exist "Main\sanqing_compile.log" (
    del /f /q "Main\sanqing_compile.log"
    echo Deleted: Main\sanqing_compile.log
)

echo Cleanup complete.
