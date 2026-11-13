#!/bin/bash
# ============================================================
# Đóng gói file ZIP để gửi khách (cài không cần biết GitHub).
#
#   bash mrbright/build-zip.sh      # -> ../dist/JavisMrBright-<phiên bản>.zip
#
# Gói lấy từ commit hiện tại (đã commit, không lấy file nháp), có kèm lịch sử git để nút Cập nhật
# trong Javis chạy được, và trỏ "origin" về repo của anh. Không chứa dữ liệu/khoá của máy anh.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="$(command -v python3 || command -v python)"
"$PY" mrbright/apply.py --kiem
REPO="$("$PY" -c 'import json;print(json.load(open("mrbright/brand.json"))["repo"])')"
VER="$(cat VERSION)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
OUT="$(cd "$ROOT/.." && pwd)/dist/JavisMrBright-$VER.zip"   # ngoài repo, khỏi lỡ commit
mkdir -p "$(dirname "$OUT")" "$TMP/JavisMrBright-$VER"
PKG="$TMP/JavisMrBright-$VER"

git clone -q --no-hardlinks "$ROOT" "$PKG/javis"
git -C "$PKG/javis" remote set-url origin "https://github.com/$REPO.git"
git -C "$PKG/javis" gc -q --prune=now 2>/dev/null || true
cp "$PKG/javis/mrbright/install/CAI-DAT-WINDOWS.bat" "$PKG/javis/mrbright/install/CAI-DAT-MAC.command" "$PKG/"
chmod +x "$PKG/CAI-DAT-MAC.command"
cat > "$PKG/HUONG-DAN-CAI-DAT.txt" <<'EOF'
CAI DAT JAVIS
=============
Can: may tinh co mang Internet, khoang 3 GB trong. Thoi gian: 10-30 phut.

WINDOWS
  1. Giai nen file ZIP (chuot phai > Extract All).
  2. Bam dup CAI-DAT-WINDOWS.bat. Neu Windows hien "Windows protected your PC":
     bam "More info" > "Run anyway".
  3. Cho cua so cai dat chay xong. Javis tu mo, tren Desktop co bieu tuong "Javis".

MAC
  1. Bam dup file ZIP de giai nen.
  2. Chuot phai CAI-DAT-MAC.command > Open > Open (lan dau macOS hoi xac nhan).
  3. Neu macOS hoi cai "Command Line Tools": bam Install va cho tai xong.
  4. Cho cai xong. Javis tu mo, tren Desktop co bieu tuong "Javis".

DUNG THU VA KICH HOAT
  - Javis dung thu 7 ngay ke tu lan chay dau.
  - De kich hoat: mo Javis, bam "Nhap ma kich hoat" (hoac vao dia chi /mrb),
    chep MA MAY gui nha cung cap, dan ma kich hoat nhan duoc vao o, bam Kich hoat.
EOF
perl -pi -e 's/\r?\n/\r\n/' "$PKG/HUONG-DAN-CAI-DAT.txt"   # Notepad cũ cần CRLF
(cd "$TMP" && rm -f "$OUT" && zip -qry "$OUT" "JavisMrBright-$VER")
echo "Đã tạo: $OUT ($(du -h "$OUT" | cut -f1))"
