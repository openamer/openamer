# detect-monitors.ps1 — Run this from PowerShell (not bash) to detect all monitors
# Usage: powershell.exe -File "C:\Users\damir\AppData\Local\openamer-laptop\scripts\detect-monitors.ps1"

Add-Type -AssemblyName System.Windows.Forms

Write-Host "=== Monitor Detection ==="
Write-Host ""

$screens = [System.Windows.Forms.Screen]::AllScreens
Write-Host "Total monitors: $($screens.Length)"
Write-Host ""

for ($i = 0; $i -lt $screens.Length; $i++) {
    $s = $screens[$i]
    Write-Host "Monitor $($i + 1):"
    Write-Host "  DeviceName : $($s.DeviceName)"
    Write-Host "  Bounds     : $($s.Bounds.Width) x $($s.Bounds.Height) at ($($s.Bounds.X), $($s.Bounds.Y))"
    Write-Host "  WorkingArea: $($s.WorkingArea.Width) x $($s.WorkingArea.Height) at ($($s.WorkingArea.X), $($s.WorkingArea.Y))"
    Write-Host "  Primary    : $($s.Primary)"
    Write-Host "  BitsPerPixel: $($s.BitsPerPixel)"
    Write-Host ""
}

# Compute the virtual desktop bounds (union of all monitors)
$minX = ($screens | ForEach-Object { $_.Bounds.X } | Measure-Object -Minimum).Minimum
$minY = ($screens | ForEach-Object { $_.Bounds.Y } | Measure-Object -Minimum).Minimum
$maxX = ($screens | ForEach-Object { $_.Bounds.Right } | Measure-Object -Maximum).Maximum
$maxY = ($screens | ForEach-Object { $_.Bounds.Bottom } | Measure-Object -Maximum).Maximum

Write-Host "Virtual Desktop:"
Write-Host "  Total size   : $(($maxX - $minX)) x $(($maxY - $minY))"
Write-Host "  Full bounds  : ($minX, $minY) to ($maxX, $maxY)"

# Compute offset for each non-primary monitor
$primary = $screens | Where-Object { $_.Primary -eq $true }
if ($primary) {
    Write-Host ""
    Write-Host "Coordinate Offsets (add to capture coordinates for secondary monitors):"
    foreach ($s in $screens) {
        if (-not $s.Primary) {
            Write-Host "  Secondary '$($s.DeviceName)':"
            Write-Host "    Offset X: +$($s.Bounds.X - $primary.Bounds.X)  (add to primary-anchored x)"
            Write-Host "    Offset Y: +$($s.Bounds.Y - $primary.Bounds.Y)  (add to primary-anchored y)"
            Write-Host "    To capture this monitor alone, use region: ($($s.Bounds.X),$($s.Bounds.Y)) to ($($s.Bounds.Right),$($s.Bounds.Bottom))"
        }
    }
}

# JSON output for programmatic use
Write-Host ""
Write-Host "=== JSON ==="
$result = @{
    count = $screens.Length
    monitors = @()
    virtualDesktop = @{
        minX = $minX
        minY = $minY
        maxX = $maxX
        maxY = $maxY
        width = $maxX - $minX
        height = $maxY - $minY
    }
}
foreach ($s in $screens) {
    $result.monitors += @{
        deviceName = $s.DeviceName
        width = $s.Bounds.Width
        height = $s.Bounds.Height
        x = $s.Bounds.X
        y = $s.Bounds.Y
        workingWidth = $s.WorkingArea.Width
        workingHeight = $s.WorkingArea.Height
        workingX = $s.WorkingArea.X
        workingY = $s.WorkingArea.Y
        primary = $s.Primary
        bitsPerPixel = $s.BitsPerPixel
    }
}
Write-Host ($result | ConvertTo-Json -Compress)