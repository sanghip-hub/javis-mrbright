#!/bin/bash
# Bam chuot phai > Open de cai Javis tren Mac. Can mang Internet (tai Python, Node, thu vien).
DIR="$(cd "$(dirname "$0")" && pwd)"
xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
bash "$DIR/javis/mrbright/install/cai-mac.sh" "$DIR/javis"
echo ""
read -r -p "Nhan Enter de dong cua so..." _
