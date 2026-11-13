#!/bin/bash
# ============================================================
# JAVIS MR BRIGHT - CAI DAT 1 CU BAM TREN MAC
#
# Cach 1 (co mang): mo Terminal, dan:
#   curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/mrbright/install/cai-mac.sh | bash
# Cach 2 (tu file ZIP): giai nen, bam chuot phai CAI-DAT-MAC.command > Open
#
# Cai vao ~/JavisOS. Dung lai bo cai goc cua Javis (packaging/macos/bootstrap.sh: Git, Python,
# Node, cac bo nao AI, venv, tu khoi dong), chi doi nguon tai ve repo cua Javis Mr Bright.
# ============================================================
set -u
REPO="https://github.com/OWNER/REPO.git"   # MRB_REPO (mrbright/apply.py tu dien)
BRANCH="main"                              # MRB_BRANCH
NGUON="${1:-}"                             # thu muc ma nguon trong goi ZIP (CAI-DAT-MAC.command truyen vao)
export JAVIS_HOME="${JAVIS_HOME:-$HOME/JavisOS}"
export JAVIS_REPO="$REPO" JAVIS_BRANCH="$BRANCH"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()  { echo -e "    ${GREEN}OK${NC}  $*"; }
err() { echo -e "    ${RED}[LOI]${NC} $*"; }

echo ""
echo -e "${CYAN} ==========================================${NC}"
echo -e "${CYAN}  JAVIS - cai dat tu dong (10-30 phut)${NC}"
echo -e "${CYAN}  Thu muc cai: $JAVIS_HOME${NC}"
echo -e "${CYAN} ==========================================${NC}"

if [ -n "$NGUON" ] && [ -f "$NGUON/server/main.py" ]; then
  if [ -d "$JAVIS_HOME/.git" ]; then
    ok "Da co Javis o $JAVIS_HOME, giu nguyen du lieu"
  elif [ -e "$JAVIS_HOME" ] && [ -n "$(ls -A "$JAVIS_HOME" 2>/dev/null)" ]; then
    err "Thu muc $JAVIS_HOME da co file khac. Doi ten thu muc do roi chay lai."; exit 1
  else
    echo "    Dang chep ma nguon vao $JAVIS_HOME ..."
    mkdir -p "$JAVIS_HOME" && (cd "$NGUON" && tar --exclude=.venv --exclude=node_modules --exclude=__pycache__ -cf - .) | (cd "$JAVIS_HOME" && tar -xf -)
    [ -f "$JAVIS_HOME/server/main.py" ] || { err "Chep ma nguon that bai."; exit 1; }
    # Goi tai tu trinh duyet bi gan co "quarantine": go co de macOS khong chan cac script cai dat.
    xattr -dr com.apple.quarantine "$JAVIS_HOME" 2>/dev/null || true
    chmod +x "$JAVIS_HOME"/*.command "$JAVIS_HOME"/*.sh "$JAVIS_HOME"/bin/*.sh 2>/dev/null || true
    ok "Da chep ma nguon"
  fi
  BOOT="$JAVIS_HOME/packaging/macos/bootstrap.sh"
else
  BOOT="$(mktemp -t javis-mrb-bootstrap).sh"
  RAW="$(echo "$REPO" | sed -e 's#^https://github.com/#https://raw.githubusercontent.com/#' -e 's#\.git$##')/$BRANCH/packaging/macos/bootstrap.sh"
  curl -fsSL "$RAW" -o "$BOOT" || { err "Khong tai duoc bo cai. Kiem tra mang Internet."; exit 1; }
fi

# bootstrap.sh goc: Git, Python, clone (bo qua neu da co), install.sh (Node, CLI, venv, tu khoi dong, mo Javis)
bash "$BOOT" || { err "Cai dat chua xong. Chup man hinh nay gui nha cung cap."; exit 1; }

# Bieu tuong tren Desktop
if [ -d "$JAVIS_HOME/JAVIS OS.app" ]; then
  ln -sfn "$JAVIS_HOME/JAVIS OS.app" "$HOME/Desktop/Javis.app" 2>/dev/null && ok "Da tao bieu tuong Javis tren Desktop"
fi
echo ""
ok "XONG. Ban dung thu 7 ngay. Can ma kich hoat: lien he nha cung cap."
