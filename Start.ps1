param([switch]$Check)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CapturePolicy {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool SetWindowDisplayAffinity(IntPtr handle, uint affinity);
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool GetWindowDisplayAffinity(IntPtr handle, out uint affinity);
}
'@
[System.Windows.Forms.Application]::EnableVisualStyles()
$editor = New-Object System.Windows.Forms.Form
$editor.Text = 'Interview Prompter - Prototype'
$editor.Size = New-Object System.Drawing.Size(850,650)
$editor.StartPosition = 'CenterScreen'
$editor.BackColor = [System.Drawing.Color]::FromArgb(24,28,36)
$editor.ForeColor = [System.Drawing.Color]::White
$header = New-Object System.Windows.Forms.Label
$header.Text = "INTERVIEW PROMPTER | Milestone 1`r`nManual notes prototype. Live audio and AI are not connected."
$header.SetBounds(20,15,790,48)
$editor.Controls.Add($header)
$notes = New-Object System.Windows.Forms.RichTextBox
$notes.SetBounds(20,75,790,380)
$notes.Anchor = 'Top,Bottom,Left,Right'
$notes.Font = New-Object System.Drawing.Font('Segoe UI',16)
$notes.Text = "Prepare your notes here.`n`nUse concise points, examples and verified achievements.`n`nShow prompter to begin."
$editor.Controls.Add($notes)
$show = New-Object System.Windows.Forms.Button
$show.Text = 'Show / update prompter'
$show.SetBounds(20,475,220,38)
$show.Anchor = 'Bottom,Left'
$editor.Controls.Add($show)
$load = New-Object System.Windows.Forms.Button
$load.Text = 'Import text notes'
$load.SetBounds(255,475,150,38)
$load.Anchor = 'Bottom,Left'
$editor.Controls.Add($load)
$status = New-Object System.Windows.Forms.Label
$status.Text = "Capture exclusion: unverified.`r`nThe editor is visible in screen shares. Verify the prompter from a receiving device."
$status.SetBounds(20,530,790,65)
$status.Anchor = 'Bottom,Left,Right'
$editor.Controls.Add($status)
$overlay = New-Object System.Windows.Forms.Form
$overlay.Text = 'Prompter - capture compatibility unverified'
$overlay.Size = New-Object System.Drawing.Size(740,330)
$overlay.FormBorderStyle = 'None'
$overlay.ShowInTaskbar = $false
$overlay.StartPosition = 'Manual'
$overlay.Opacity = 0.94
$overlay.Padding = New-Object System.Windows.Forms.Padding(24,12,24,14)
$shape = New-Object System.Drawing.Drawing2D.GraphicsPath
$shape.AddArc(0,0,40,40,180,90)
$shape.AddArc(699,0,40,40,270,90)
$shape.AddArc(699,289,40,40,0,90)
$shape.AddArc(0,289,40,40,90,90)
$shape.CloseFigure()
$overlay.Region = New-Object System.Drawing.Region($shape)
$shape.Dispose()
$overlay.Add_Paint({
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(95,190,210,240),1)
    $_.Graphics.DrawLine($pen,30,1,710,1)
    $pen.Dispose()
})
$caption = New-Object System.Windows.Forms.Label
$caption.Text = '  TELEPROMPTER                                      NOTES  /  PREVIEW'
$caption.Dock = 'Top'
$caption.Height = 38
$caption.Font = New-Object System.Drawing.Font('Segoe UI',10)
$caption.ForeColor = [System.Drawing.Color]::FromArgb(164,185,212)
$overlay.Controls.Add($caption)
$motion = New-Object System.Windows.Forms.Timer
$motion.Interval = 15
$script:motionStart = [DateTime]::UtcNow
$script:closingPanel = $false
$script:panelTop = 12
$animate = {
    param([bool]$closing)
    $motion.Stop()
    $script:closingPanel = $closing
    $script:motionStart = [DateTime]::UtcNow
    $screen = [System.Windows.Forms.Screen]::FromControl($editor).WorkingArea
    $script:panelTop = $screen.Top + 12
    $overlay.Left = $screen.Left + [int](($screen.Width - $overlay.Width)/2)
    if (-not $closing) { $overlay.Top = $script:panelTop - $overlay.Height; $overlay.Opacity = 0.05; $overlay.Show() }
    $motion.Start()
}
$motion.Add_Tick({
    $t = [Math]::Min(1,([DateTime]::UtcNow-$script:motionStart).TotalMilliseconds/380)
    $ease = 1-[Math]::Pow(1-$t,3)
    if ($script:closingPanel) { $progress = 1-$ease } else { $progress = $ease }
    $overlay.Top = [int]($script:panelTop - (1-$progress)*($overlay.Height+12))
    $overlay.Opacity = [Math]::Max(0.02,0.94*$progress)
    if ($t -ge 1) { $motion.Stop(); if ($script:closingPanel) { $overlay.Hide() } }
})
$overlay.TopMost = $true
$overlay.BackColor = [System.Drawing.Color]::FromArgb(25,31,44)
$overlay.ForeColor = [System.Drawing.Color]::White
$overlay.KeyPreview = $true
$bar = New-Object System.Windows.Forms.FlowLayoutPanel
$bar.Dock = 'Bottom'
$bar.Height = 38
$bar.Padding = New-Object System.Windows.Forms.Padding(0,4,0,0)
$overlay.Controls.Add($bar)
$reader = New-Object System.Windows.Forms.RichTextBox
$reader.Dock = 'Fill'
$reader.ReadOnly = $true
$reader.BackColor = $overlay.BackColor
$reader.ForeColor = $overlay.ForeColor
$reader.Font = New-Object System.Drawing.Font('Segoe UI',22)
$reader.BorderStyle = 'None'
$overlay.Controls.Add($reader)
$reader.BringToFront()
$caption.BringToFront()
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 80
$timer.Add_Tick({
    if ($reader.SelectionStart -lt $reader.TextLength) {
        $reader.SelectionStart += 1
        $reader.ScrollToCaret()
    } else { $timer.Stop() }
})
foreach ($label in @('Play / pause','Restart','Font +','Font -','Hide')) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $label
    $button.Width = 124
    $button.Height = 32
    $button.ForeColor = [System.Drawing.Color]::FromArgb(220,230,245)
    $button.BackColor = [System.Drawing.Color]::FromArgb(40,49,65)
    $button.FlatStyle = 'Flat'
    $button.FlatAppearance.BorderSize = 0
    $button.Font = New-Object System.Drawing.Font('Segoe UI',9)
    $button.Cursor = [System.Windows.Forms.Cursors]::Hand
    $button.Add_Click({
        switch ($this.Text) {
            'Play / pause' { if ($timer.Enabled) { $timer.Stop() } else { $timer.Start() } }
            'Restart' { $reader.SelectionStart = 0; $reader.ScrollToCaret() }
            'Font +' { $reader.Font = New-Object System.Drawing.Font('Segoe UI',([Math]::Min(60,$reader.Font.Size+2))) }
            'Font -' { $reader.Font = New-Object System.Drawing.Font('Segoe UI',([Math]::Max(14,$reader.Font.Size-2))) }
            'Hide' { $timer.Stop(); & $animate $true }
        }
    })
    $bar.Controls.Add($button)
}
$protect = {
    $ok = [CapturePolicy]::SetWindowDisplayAffinity($overlay.Handle,0x11)
    $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    [uint32]$actual = 0
    $readback = [CapturePolicy]::GetWindowDisplayAffinity($overlay.Handle,[ref]$actual)
    if ($ok -and $readback -and $actual -eq 0x11) {
        $status.Text = "OS accepted capture exclusion; receiver-side verification still required.`r`nThis does not hide the process. The editor remains capture-visible."
    } else {
        $status.Text = "Capture exclusion unavailable (Win32 error $errorCode). Do not assume the overlay is hidden."
        throw 'Capture exclusion was not accepted. Prompter will remain hidden.'
    }
}
$overlay.Add_HandleCreated({ & $protect })
$overlay.Add_FormClosing({
    if ($_.CloseReason -eq [System.Windows.Forms.CloseReason]::UserClosing) {
        $_.Cancel = $true
        $timer.Stop()
        & $animate $true
    }
})
$overlay.Add_KeyDown({ if ($_.KeyCode -eq 'Escape') { $timer.Stop(); & $animate $true } })
$show.Add_Click({
    try {
        $reader.Text = ''
        $null = $overlay.Handle
        & $protect
        & $animate $false
        # Delay sensitive text until a later UI cycle; this is not a capture guarantee.
        $overlay.BeginInvoke([Action]{ $reader.Text = $notes.Text }) | Out-Null
    } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message) | Out-Null }
})
$load.Add_Click({
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = 'Text files (*.txt)|*.txt'
    if ($dialog.ShowDialog() -eq 'OK') { $notes.Text = [IO.File]::ReadAllText($dialog.FileName) }
    $dialog.Dispose()
})
$editor.Add_FormClosed({ $motion.Dispose(); $timer.Dispose(); $overlay.Dispose() })
if ($Check) {
    $null = $overlay.Handle
    & $protect
    Write-Output $status.Text
    $timer.Dispose()
    $overlay.Dispose()
    $editor.Dispose()
    exit
}
[System.Windows.Forms.Application]::Run($editor)
