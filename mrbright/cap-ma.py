#!/usr/bin/env python3
"""Công cụ CẤP MÃ KÍCH HOẠT Javis Mr Bright - chỉ chạy trên máy của anh, KHÔNG gửi cho khách.

  python3 cap-ma.py tao-khoa
      Tạo cặp khoá (một lần duy nhất). Khoá bí mật lưu ở ~/.javis-mrbright/khoa-bi-mat.pem.
      In ra khoá công khai -> dán vào mrbright/brand.json mục "public_key".

  python3 cap-ma.py cap --may ABCD-EFGH-IJKL-MNOP --ngay 30 --ten "Cong ty A"
  python3 cap-ma.py cap --may ABCD-EFGH-IJKL-MNOP --den 2027-12-31 --ten "Cong ty A"
  python3 cap-ma.py cap --may ABCD-EFGH-IJKL-MNOP --vinh-vien --ten "Cong ty A"
      In ra mã kích hoạt để gửi khách. Mỗi lần cấp được ghi vào ~/.javis-mrbright/so-cap-ma.csv.

  python3 cap-ma.py xem --ma JMB1.xxx.yyy
      Xem trong mã có gì (máy, hạn, khách) và kiểm chữ ký.

MẤT FILE khoa-bi-mat.pem = không cấp được mã mới cho các bản đã cài. Hãy sao lưu nó (USB, két mật khẩu).
LỘ FILE đó = ai cũng tự cấp mã được. Không đưa vào git, không gửi qua Zalo/email.
Cần thư viện: pip install cryptography
"""
import argparse
import base64
import csv
import datetime as dt
import json
import os
import secrets
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

THU_MUC = Path(os.getenv("MRB_KEY_DIR", str(Path.home() / ".javis-mrbright")))
KHOA = THU_MUC / "khoa-bi-mat.pem"
SO = THU_MUC / "so-cap-ma.csv"
TIEN_TO = "JMB1"


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def doc_khoa() -> Ed25519PrivateKey:
    if not KHOA.exists():
        sys.exit("Chưa có khoá. Chạy: python3 cap-ma.py tao-khoa")
    return serialization.load_pem_private_key(KHOA.read_bytes(), password=None)


def khoa_cong_khai(k: Ed25519PrivateKey) -> str:
    return b64e(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def tao_khoa(_a):
    if KHOA.exists():
        print("Đã có khoá ở", KHOA, "- KHÔNG tạo lại (tạo lại thì mọi mã cũ hết dùng được).")
        print("Khoá công khai:", khoa_cong_khai(doc_khoa()))
        return
    THU_MUC.mkdir(parents=True, exist_ok=True)
    k = Ed25519PrivateKey.generate()
    KHOA.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    try:
        os.chmod(KHOA, 0o600)
    except OSError:
        pass
    print("Đã tạo khoá bí mật:", KHOA)
    print("HÃY SAO LƯU FILE NÀY. Mất nó là không cấp được mã cho khách đã cài.")
    print("Khoá công khai (dán vào brand.json -> public_key):")
    print(khoa_cong_khai(k))


def chuan_may(s: str) -> str:
    s = "".join(ch for ch in (s or "").upper() if ch.isalnum())
    if len(s) != 16:
        sys.exit("Mã máy phải có 16 ký tự (dạng XXXX-XXXX-XXXX-XXXX).")
    return "-".join(s[i:i + 4] for i in range(0, 16, 4))


def cap(a):
    k = doc_khoa()
    may = chuan_may(a.may)
    now = int(time.time())
    if a.vinh_vien:
        han = 0
    elif a.den:
        d = dt.datetime.strptime(a.den, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        han = int(d.timestamp())
    elif a.ngay:
        han = now + int(a.ngay) * 86400
    else:
        sys.exit("Chọn một trong: --ngay N, --den YYYY-MM-DD, --vinh-vien")
    p = {"m": may, "e": han, "n": a.ten or "", "i": now, "id": secrets.token_hex(4)}
    p_b64 = b64e(json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode())
    thong_diep = TIEN_TO + "." + p_b64
    ma = thong_diep + "." + b64e(k.sign(thong_diep.encode()))
    THU_MUC.mkdir(parents=True, exist_ok=True)
    moi = not SO.exists()
    with SO.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if moi:
            w.writerow(["ngay_cap", "khach", "ma_may", "het_han", "id", "ma"])
        w.writerow([dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"), p["n"], may,
                    "vinh vien" if han == 0 else dt.datetime.fromtimestamp(han).strftime("%Y-%m-%d"), p["id"], ma])
    print("Khách:", p["n"] or "(không tên)", "| Máy:", may, "| Hạn:",
          "vĩnh viễn" if han == 0 else dt.datetime.fromtimestamp(han).strftime("%d/%m/%Y"))
    print()
    print(ma)


def xem(a):
    ma = "".join(a.ma.split())
    try:
        tt, p_b64, sig = ma.split(".")
        p = json.loads(b64d(p_b64))
    except Exception:  # noqa: BLE001
        sys.exit("Mã không đúng định dạng.")
    try:
        doc_khoa().public_key().verify(b64d(sig), (tt + "." + p_b64).encode())
        ok = "ĐÚNG (do khoá của anh ký)"
    except Exception:  # noqa: BLE001
        ok = "SAI - không phải mã do khoá này ký"
    print("Chữ ký:", ok)
    print("Máy:", p.get("m"), "| Khách:", p.get("n"), "| Cấp:", dt.datetime.fromtimestamp(p.get("i", 0)).strftime("%d/%m/%Y"),
          "| Hạn:", "vĩnh viễn" if not p.get("e") else dt.datetime.fromtimestamp(p["e"]).strftime("%d/%m/%Y"))


def main():
    ap = argparse.ArgumentParser(description="Cấp mã kích hoạt Javis Mr Bright")
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("tao-khoa").set_defaults(f=tao_khoa)
    c = sub.add_parser("cap")
    c.add_argument("--may", required=True, help="Mã máy khách gửi, dạng XXXX-XXXX-XXXX-XXXX")
    c.add_argument("--ngay", type=int, help="Số ngày dùng tính từ hôm nay")
    c.add_argument("--den", help="Dùng đến ngày YYYY-MM-DD")
    c.add_argument("--vinh-vien", action="store_true")
    c.add_argument("--ten", default="", help="Tên khách (hiện trong Javis)")
    c.set_defaults(f=cap)
    x = sub.add_parser("xem")
    x.add_argument("--ma", required=True)
    x.set_defaults(f=xem)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
