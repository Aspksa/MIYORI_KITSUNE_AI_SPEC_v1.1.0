$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 may otherwise negotiate obsolete TLS defaults.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {
    # PowerShell 7+ / modern runtimes already use secure defaults.
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "runtime"
$Temp = Join-Path $Root ".portable-setup"

$PythonVersion = "3.12.10"
$PythonZipName = "python-$PythonVersion-embeddable-amd64.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonZipName"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

Write-Host ""
Write-Host "Miyori portable runtime setup"
Write-Host "Python $PythonVersion x64"
Write-Host ""

if (Test-Path (Join-Path $Runtime "python.exe")) {
    Write-Host "Portable runtime already exists."
    exit 0
}

if (Test-Path $Temp) {
    Remove-Item $Temp -Recurse -Force
}
New-Item -ItemType Directory -Path $Temp | Out-Null
New-Item -ItemType Directory -Path $Runtime -Force | Out-Null

$ZipPath = Join-Path $Temp $PythonZipName
$GetPipPath = Join-Path $Temp "get-pip.py"

try {
    Write-Host "[1/4] Downloading official Python embeddable package..."
    Invoke-WebRequest -Uri $PythonUrl -OutFile $ZipPath -UseBasicParsing

    Write-Host "[2/4] Extracting runtime..."
    Expand-Archive -Path $ZipPath -DestinationPath $Runtime -Force

    $Pth = Get-ChildItem -Path $Runtime -Filter "python*._pth" | Select-Object -First 1
    if (-not $Pth) {
        throw "Python ._pth configuration file was not found."
    }

    $Lines = Get-Content $Pth.FullName
    $Updated = @()
    $HasSitePackages = $false
    foreach ($Line in $Lines) {
        if ($Line.Trim() -eq "#import site") {
            $Updated += "import site"
        } else {
            $Updated += $Line
        }
        if ($Line.Trim() -eq "Lib\site-packages") {
            $HasSitePackages = $true
        }
    }
    if (-not $HasSitePackages) {
        $Updated += "Lib\site-packages"
    }
    Set-Content -Path $Pth.FullName -Value $Updated -Encoding ASCII

    $PythonExe = Join-Path $Runtime "python.exe"
    & $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Downloaded Python runtime is incompatible with Miyori."
    }

    Write-Host "[3/4] Installing pip..."
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath -UseBasicParsing
    & $PythonExe $GetPipPath --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        throw "pip installation failed with exit code $LASTEXITCODE."
    }

    Write-Host "[4/4] Installing Miyori dependencies..."
    & $PythonExe -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed with exit code $LASTEXITCODE."
    }

    Write-Host ""
    Write-Host "Portable runtime is ready: $Runtime"
    Write-Host "The whole Miyori folder can now be moved to another drive or USB storage."
}
finally {
    if (Test-Path $Temp) {
        Remove-Item $Temp -Recurse -Force
    }
}
