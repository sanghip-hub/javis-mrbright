#!/usr/bin/env python3
"""Áp phần tuỳ biến Javis Mr Bright lên mã nguồn Javis OS gốc. Chạy lại bao nhiêu lần cũng được.

  python3 mrbright/apply.py            # áp vào repo chứa thư mục mrbright/
  python3 mrbright/apply.py --kiem     # chỉ kiểm, không sửa (trả mã lỗi 1 nếu còn thiếu)

Làm gì:
  1. Chép server/ban_quyen.py, dashboard/mrb-banner.js vào cây Javis, điền cấu hình từ brand.json.
  2. server/main.py: nối khoá bản quyền (đầu file + cuối file), đổi GITHUB_REPO sang repo của anh.
  3. server/updater.py: nút Cập nhật kéo code từ repo của anh thay vì repo gốc.
  4. dashboard/index.html: bỏ lời mời "Tặng sao" và dòng "by Javis Foundation", thêm thanh báo dùng thử.
  5. ANNOUNCEMENTS.json: để trống (thông báo của repo gốc không hiện cho khách).
  6. packaging/*/bootstrap.*: bộ cài mặc định clone repo của anh.

Repo gốc đổi chỗ neo thì script DỪNG và báo rõ chỗ nào, không sửa nửa vời.
"""
import ast
import json
import re
import shutil
import sys
from pathlib import Path

MRB = Path(__file__).resolve().parent
ROOT = MRB.parent
CFG = json.loads((MRB / "brand.json").read_text(encoding="utf-8"))
REPO = CFG["repo"].strip()
BRANCH = (CFG.get("branch") or "main").strip()
CHI_KIEM = "--kiem" in sys.argv
loi, da_sua = [], []

MARK_DAU = "import ban_quyen as _mrb_ban_quyen  # Javis Mr Bright: khoá bản quyền (mrbright/apply.py)"
MARK_CUOI = "_mrb_ban_quyen.gan_vao(app)  # Javis Mr Bright (mrbright/apply.py)"
BANNER = '<script src="/static/mrb-banner.js?v=1"></script>'


def doc(p):
    return (ROOT / p).read_text(encoding="utf-8")


def ghi(p, text, mo_ta):
    if (ROOT / p).read_text(encoding="utf-8") != text:
        da_sua.append(mo_ta)
        if not CHI_KIEM:
            # Giữ kiểu xuống dòng của file gốc (.ps1/.bat của repo là CRLF).
            nl = "\r\n" if b"\r\n" in (ROOT / p).read_bytes() else "\n"
            (ROOT / p).write_text(text, encoding="utf-8", newline=nl)


def kiem_cau_hinh():
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", REPO) or REPO.startswith("OWNER/"):
        loi.append('brand.json: "repo" chưa điền (dạng ten-github/ten-repo).')
    if len(CFG.get("public_key") or "") < 40:
        loi.append('brand.json: "public_key" chưa điền (chạy mrbright/cap-ma.py tao-khoa trên máy anh).')


def chep_file():
    src = (MRB / "server" / "ban_quyen.py").read_text(encoding="utf-8")
    thay = {
        "__MRB_PUBLIC_KEY__": CFG.get("public_key") or "",
        "__MRB_TEN__": CFG.get("ten") or "Javis",
        "__MRB_LIEN_HE__": CFG.get("lien_he") or "",
    }
    for k, v in thay.items():
        src = src.replace('"' + k + '"', json.dumps(v, ensure_ascii=False))
    src = re.sub(r"^SO_NGAY_DUNG_THU = \d+", "SO_NGAY_DUNG_THU = %d" % int(CFG.get("so_ngay_dung_thu") or 7),
                 src, count=1, flags=re.M)
    dich = ROOT / "server" / "ban_quyen.py"
    if not dich.exists() or dich.read_text(encoding="utf-8") != src:
        da_sua.append("server/ban_quyen.py")
        if not CHI_KIEM:
            dich.write_text(src, encoding="utf-8", newline="\n")
    b_src, b_dich = MRB / "dashboard" / "mrb-banner.js", ROOT / "dashboard" / "mrb-banner.js"
    if not b_dich.exists() or b_dich.read_bytes() != b_src.read_bytes():
        da_sua.append("dashboard/mrb-banner.js")
        if not CHI_KIEM:
            shutil.copyfile(b_src, b_dich)


def va_main():
    p = "server/main.py"
    t = doc(p)
    if MARK_DAU not in t:
        mod = ast.parse(t)
        if not (mod.body and isinstance(mod.body[0], ast.Expr) and isinstance(getattr(mod.body[0], "value", None), ast.Constant)):
            loi.append(p + ": không thấy docstring đầu file để chèn khoá.")
            return
        dong = t.split("\n")
        n = mod.body[0].end_lineno
        dong[n:n] = [MARK_DAU, "_mrb_ban_quyen.chan_neu_khoa()  # hết hạn thì dừng ở đây, Javis không được nạp"]
        t = "\n".join(dong)
    if MARK_CUOI not in t:
        t = t.rstrip("\n") + "\n\n\n" + MARK_CUOI + "\n"
    t2, n = re.subn(r'^GITHUB_REPO = "[^"]*"', 'GITHUB_REPO = "%s"' % REPO, t, count=1, flags=re.M)
    if n != 1:
        loi.append(p + ": không thấy dòng GITHUB_REPO.")
    ghi(p, t2, p)


def va_updater():
    p = "server/updater.py"
    t = doc(p)
    m = re.search(r"def release_source\(\):.*?\n    return \"[^\"]*\", \"[^\"]*\"", t, flags=re.S)
    if not m:
        loi.append(p + ": không thấy hàm release_source().")
        return
    moi = re.sub(r'return "[^"]*", "[^"]*"', 'return "https://github.com/%s.git", "%s"' % (REPO, BRANCH), m.group(0))
    ghi(p, t[:m.start()] + moi + t[m.end():], p)


def va_index():
    p = "dashboard/index.html"
    t = doc(p)
    giu = []
    for line in t.split("\n"):
        s = line.strip()
        if ("star-nudge.css" in s or "star-nudge.js" in s) and s.startswith("<"):
            continue
        if s.startswith("<!--") and "tặng sao" in s.lower():
            continue
        if 'class="rf-author"' in s:
            continue
        giu.append(line)
    t2 = "\n".join(giu)
    if BANNER not in t2:
        if "</body>" not in t2:
            loi.append(p + ": không thấy </body>.")
            return
        t2 = t2.replace("</body>", "  " + BANNER + "\n</body>", 1)
    ghi(p, t2, p)


def va_announcements():
    p = "ANNOUNCEMENTS.json"
    if not (ROOT / p).exists():
        return
    try:
        d = json.loads(doc(p))
    except ValueError:
        d = {}
    if d.get("announcements"):
        ghi(p, json.dumps({"format_version": d.get("format_version", 1), "announcements": []}, indent=2) + "\n", p)


def va_bootstrap():
    url = "https://github.com/%s.git" % REPO
    for p, pat, rep in (
        ("packaging/windows/bootstrap.ps1", r'\[string\]\$Repo = "[^"]*"', '[string]$Repo = "%s"' % url),
        ("packaging/macos/bootstrap.sh", r'REPO="\$\{JAVIS_REPO:-[^}]*\}"', 'REPO="${JAVIS_REPO:-%s}"' % url),
    ):
        if not (ROOT / p).exists():
            loi.append(p + ": không còn file này.")
            continue
        t = doc(p)
        t2, n = re.subn(pat, rep.replace("\\", "\\\\"), t, count=1)
        if n != 1:
            loi.append(p + ": không thấy dòng repo mặc định.")
            continue
        ghi(p, t2, p)


def va_install():
    """Bộ cài 1 cú bấm (mrbright/install): điền repo + nhánh vào dòng có nhãn MRB_REPO / MRB_BRANCH."""
    url = "https://github.com/%s.git" % REPO
    for p in ("mrbright/install/cai-windows.ps1", "mrbright/install/cai-mac.sh"):
        t = doc(p)
        t2 = re.sub(r'"[^"]*"(\s*#\s*MRB_REPO)', lambda m: '"%s"%s' % (url, m.group(1)), t)
        t2 = re.sub(r'"[^"]*"(\s*#\s*MRB_BRANCH)', lambda m: '"%s"%s' % (BRANCH, m.group(1)), t2)
        t2 = t2.replace("raw.githubusercontent.com/OWNER/REPO/", "raw.githubusercontent.com/%s/" % REPO)
        t2 = re.sub(r"raw\.githubusercontent\.com/[^/\s]+/[^/\s]+/main/mrbright",
                    "raw.githubusercontent.com/%s/%s/mrbright" % (REPO, BRANCH), t2)
        if "MRB_REPO" not in t2:
            loi.append(p + ": mất nhãn MRB_REPO.")
            continue
        ghi(p, t2, p)


def main():
    kiem_cau_hinh()
    if loi and not CHI_KIEM:
        for l in loi:
            print("[LỖI]", l)
        sys.exit(1)
    chep_file()
    va_main()
    va_updater()
    va_index()
    va_announcements()
    va_bootstrap()
    va_install()
    if loi:
        for l in loi:
            print("[LỖI]", l)
        print("Repo gốc đã đổi cấu trúc ở chỗ trên. Cần sửa mrbright/apply.py trước khi phát hành.")
        sys.exit(1)
    if CHI_KIEM:
        if da_sua:
            print("Còn thiếu:", ", ".join(da_sua))
            sys.exit(1)
        print("OK: mọi tuỳ biến Javis Mr Bright đã có.")
    else:
        print("Đã áp:" if da_sua else "Không có gì cần sửa.", ", ".join(da_sua))


if __name__ == "__main__":
    main()
