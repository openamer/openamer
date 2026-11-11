Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b = New-Object System.Drawing.Bitmap 1920,1200
$g = [System.Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen(0,0,0,0,$b.Size)
$b.Save('C:\Users\damir\AppData\Local\openamer-laptop\images\desktop_check.png')
Write-Output "saved"
