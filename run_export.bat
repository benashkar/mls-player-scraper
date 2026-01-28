@echo off
echo ============================================
echo Export Data to CSV
echo ============================================
echo.
python -c "from scrapers.view_data import export_csv; export_csv('output/players.csv')"
echo.
echo Data exported to output/players.csv
pause
