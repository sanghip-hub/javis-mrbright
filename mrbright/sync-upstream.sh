#!/bin/bash
# ============================================================
# Kéo bản mới nhất của Javis OS gốc về repo Javis Mr Bright, áp lại phần tuỳ biến, kiểm, commit.
#
#   bash mrbright/sync-upstream.sh          # kéo + áp + kiểm + commit (CHƯA push)
#   bash mrbright/sync-upstream.sh --push   # làm xong thì push luôn -> khách bấm Cập nhật là nhận
#
# Chỗ nào repo gốc và mình cùng sửa thì lấy bản gốc (-X theirs), rồi apply.py chèn lại phần của mình.
# apply.py không tìm thấy chỗ neo (repo gốc đổi cấu trúc) thì script DỪNG, không commit gì.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."
UPSTREAM="https://github.com/blogminhquy/javis-os.git"
PY="$(command -v python3 || command -v python)"

if [ -n "$(git status --porcelain)" ]; then
  echo "[LỖI] Repo đang có thay đổi chưa commit. Commit hoặc bỏ đi rồi chạy lại."; exit 1
fi
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream "$UPSTREAM"
git fetch -q upstream main
CU="$(cat VERSION 2>/dev/null || echo '?')"
git merge -q --no-edit -X theirs upstream/main -m "Đồng bộ Javis OS gốc $(git show upstream/main:VERSION 2>/dev/null)" || {
  echo "[LỖI] Merge không tự giải quyết được (thường do repo gốc xoá/đổi tên file mình sửa)."
  echo "      Xem: git status. Huỷ: git merge --abort"; exit 1; }

"$PY" mrbright/apply.py
"$PY" -m py_compile server/main.py server/ban_quyen.py server/updater.py
"$PY" mrbright/apply.py --kiem

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "Áp lại tuỳ biến Javis Mr Bright sau khi đồng bộ"
fi
MOI="$(cat VERSION)"
echo "OK: $CU -> $MOI"
if [ "${1:-}" = "--push" ]; then
  git push -q origin HEAD
  echo "Đã push. Máy khách bấm Cập nhật trong Javis sẽ nhận bản $MOI."
else
  echo "Chưa push. Nên chạy thử trên máy anh trước, rồi: git push"
fi
