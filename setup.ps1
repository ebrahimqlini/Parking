$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "The Python launcher was not found. Install Python 3.7 (64-bit) first."
}

py -3.7 --version
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.7 was not found. This legacy project uses Python 3.7-compatible wheels."
}

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    py -3.7 -m venv venv
}

$python = Join-Path (Get-Location) "venv\Scripts\python.exe"
& $python -m pip install --upgrade "pip==23.3.2"
if ($LASTEXITCODE -ne 0) { throw "Could not update pip." }

# dlib has no standard Windows wheel for this Python version; use the compatible
# prebuilt wheel, then install face-recognition without asking pip to compile dlib.
& $python -m pip install --no-deps "dlib-bin==19.24.2.post1"
if ($LASTEXITCODE -ne 0) { throw "Could not install the dlib Windows wheel." }

& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install project requirements." }

& $python -m pip install --no-deps "face-recognition==1.3.0"
if ($LASTEXITCODE -ne 0) { throw "Could not install face-recognition." }

if (-not (Test-Path ".\.env")) {
    Copy-Item ".\.env.example" ".\.env"
    Write-Host "Created .env from .env.example. Add your Firebase settings before running the app."
}

Write-Host "Setup complete. Add your private face images and Firebase key, then run: .\venv\Scripts\python.exe main.py"
