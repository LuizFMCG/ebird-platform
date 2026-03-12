Set-Location $PSScriptRoot\..
$env:PYTHONPATH = (Resolve-Path .\src).Path

if (Test-Path .\.venv\Scripts\python.exe) {
    .\.venv\Scripts\python.exe -m ebird_platform.pipeline.validate
    exit $LASTEXITCODE
}

if (Test-Path D:\eBird\.venv312\Scripts\python.exe) {
    D:\eBird\.venv312\Scripts\python.exe -m ebird_platform.pipeline.validate
    exit $LASTEXITCODE
}

throw "No virtual environment found. Create .\.venv or use D:\eBird\.venv312."
