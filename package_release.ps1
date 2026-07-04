$ErrorActionPreference = "Stop"

# 1. Automatically read version from src/gui.py
$guiContent = Get-Content "src\gui.py" -Raw
if ($guiContent -match 'APP_VERSION\s*=\s*"([^"]+)"') {
    $version = $matches[1]
    Write-Host "Detected version: $version" -ForegroundColor Green
} else {
    $version = Read-Host "Cannot automatically detect version, please enter manually (e.g. v1.8.2)"
}

# 2. Create temp directory
$releaseName = "dorm-chack-release-$version"
$tempDir = ".\$releaseName"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# 3. Copy files to package
$itemsToCopy = @(
    "Run_CPU.bat",
    "Run_GPU.bat",
    "main.py",
    "pyproject.toml",
    "uv.lock",
    "*.vbs",
    "*.md",
    "src"
)

Write-Host "Copying files..."
foreach ($item in $itemsToCopy) {
    if (Test-Path $item) {
        Copy-Item -Path $item -Destination $tempDir -Recurse -Force
    } else {
        # Try to resolve wildcards
        $resolved = Resolve-Path $item -ErrorAction SilentlyContinue
        if ($resolved) {
            foreach ($res in $resolved) {
                Copy-Item -Path $res.Path -Destination $tempDir -Recurse -Force
            }
        } else {
            Write-Host "Warning: File not found $item" -ForegroundColor Yellow
        }
    }
}

# 4. Compress to zip
$zipName = "$releaseName.zip"
if (Test-Path $zipName) {
    Remove-Item $zipName -Force
}

Write-Host "Creating zip file $zipName ..."
Compress-Archive -Path "$tempDir\*" -DestinationPath $zipName -Force

# 5. Clean up temp directory
Remove-Item $tempDir -Recurse -Force

Write-Host "Success! Packaged release is available at: $zipName" -ForegroundColor Green
Write-Host "You can upload this zip file to your GitHub Releases page." -ForegroundColor Cyan
