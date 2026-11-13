# ============================================================
# JAVIS MR BRIGHT - CAI DAT 1 CU BAM TREN WINDOWS
#
# Cach 1 (co mang, khong can file):  mo PowerShell, dan:
#   irm https://raw.githubusercontent.com/OWNER/REPO/main/mrbright/install/cai-windows.ps1 | iex
# Cach 2 (tu file ZIP): giai nen, bam dup CAI-DAT-WINDOWS.bat
#
# Cai vao %USERPROFILE%\JavisOS. Dung lai bo cai goc cua Javis (packaging/windows/bootstrap.ps1:
# Git, Python, Node, cac bo nao AI, venv, tu khoi dong cung Windows), chi doi nguon tai ve repo
# cua Javis Mr Bright. Sau do tao bieu tuong "Javis" tren Desktop va mo Javis.
#
# ASCII ONLY: Windows PowerShell 5.1 doc file khong BOM bang ANSI codepage.
# ============================================================
param(
  [string]$Nguon = "",                                           # thu muc ma nguon trong goi ZIP
  [string]$Dir = (Join-Path $env:USERPROFILE "JavisOS")
)
$Repo = "https://github.com/OWNER/REPO.git"   # MRB_REPO (mrbright/apply.py tu dien)
$Branch = "main"                              # MRB_BRANCH
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try { $Host.UI.RawUI.WindowTitle = "Javis - cai dat" } catch { }

function Ok($t) { Write-Host "    OK  $t" -ForegroundColor Green }
function Err($t) { Write-Host "    [LOI] $t" -ForegroundColor Red }
function Done($code) {
  if ($code -ne 0) { Write-Host ""; Err "Cai dat chua xong. Chup man hinh nay gui nha cung cap." }
  Read-Host "Nhan Enter de dong cua so" | Out-Null
}

Write-Host ""
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host "  JAVIS - cai dat tu dong (10-30 phut)" -ForegroundColor Cyan
Write-Host "  Thu muc cai: $Dir" -ForegroundColor Cyan
Write-Host " ==========================================" -ForegroundColor Cyan

# ---- 1. Ma nguon: tu goi ZIP (chep sang $Dir) hoac de bootstrap tai ve bang git
if ($Nguon -and (Test-Path (Join-Path $Nguon "server\main.py"))) {
  if (Test-Path (Join-Path $Dir ".git")) {
    Ok "Da co Javis o $Dir, giu nguyen du lieu"
  } elseif ((Test-Path $Dir) -and (Get-ChildItem -Force $Dir | Select-Object -First 1)) {
    Err "Thu muc $Dir da co file khac. Doi ten thu muc do roi chay lai."
    Done 1; return
  } else {
    Write-Host "    Dang chep ma nguon vao $Dir ..."
    robocopy "$Nguon" "$Dir" /E /NFL /NDL /NJH /NJS /NP /XD .venv node_modules __pycache__ | Out-Null
    if (-not (Test-Path (Join-Path $Dir "server\main.py"))) { Err "Chep ma nguon that bai."; Done 1; return }
    # File giai nen tu ZIP tai bang trinh duyet bi Windows danh dau "tu Internet": go dau de script chay em.
    Get-ChildItem -Path $Dir -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    Ok "Da chep ma nguon"
  }
  $boot = Join-Path $Dir "packaging\windows\bootstrap.ps1"
} else {
  $boot = Join-Path $env:TEMP "javis-mrb-bootstrap.ps1"
  $raw = ($Repo -replace "^https://github.com/", "https://raw.githubusercontent.com/" -replace "\.git$", "") + "/$Branch/packaging/windows/bootstrap.ps1"
  try { Invoke-WebRequest -Uri $raw -OutFile $boot -UseBasicParsing }
  catch { Err "Khong tai duoc bo cai: $($_.Exception.Message). Kiem tra mang Internet."; Done 1; return }
}

# ---- 2. Bo cai goc cua Javis: Git, Python, Node, CLI, venv, tu khoi dong
$args2 = "-NoProfile -ExecutionPolicy Bypass -File `"$boot`" -Dir `"$Dir`" -Repo `"$Repo`" -Branch `"$Branch`" -NoPause"
# Khong dung -Wait: no cho ca cac tien trinh phu bo cai de lai (xem Invoke-Capped trong bootstrap.ps1).
$p = Start-Process -FilePath (Join-Path $PSHOME "powershell.exe") -ArgumentList $args2 -NoNewWindow -PassThru
$null = $p.Handle
$p.WaitForExit()
if ($p.ExitCode -ne 0 -or -not (Test-Path (Join-Path $Dir ".venv\Scripts\python.exe"))) {
  Err "Buoc cai dat bao loi (ma $($p.ExitCode)). Doc cac dong mau do o tren."
  Done 1; return
}

# ---- 3. Bieu tuong tren Desktop
try {
  $ws = New-Object -ComObject WScript.Shell
  $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Javis.lnk"))
  $lnk.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
  $lnk.Arguments = "//nologo `"$(Join-Path $Dir 'start-javis.vbs')`" /open"
  $lnk.WorkingDirectory = $Dir
  $ico = Join-Path $Dir "packaging\assets\javis.ico"
  if (Test-Path $ico) { $lnk.IconLocation = $ico }
  $lnk.Save()
  Ok "Da tao bieu tuong Javis tren Desktop"
} catch { Err "Khong tao duoc bieu tuong Desktop: $($_.Exception.Message)" }

# ---- 4. Mo Javis
Start-Process -FilePath (Join-Path $env:WINDIR "System32\wscript.exe") -ArgumentList "//nologo `"$(Join-Path $Dir 'start-javis.vbs')`" /open" -WorkingDirectory $Dir
Write-Host ""
Ok "XONG. Javis dang mo (cho 10-20 giay). Lan sau bam bieu tuong Javis tren Desktop."
Ok "Ban dung thu 7 ngay. Can ma kich hoat: lien he nha cung cap."
Done 0
