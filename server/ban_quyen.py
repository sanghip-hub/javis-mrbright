"""Bản quyền Javis Mr Bright: dùng thử 7 ngày, sau đó cần mã kích hoạt gắn với từng máy.

CÁCH HOẠT ĐỘNG
- Lần đầu server chạy trên một máy, ngày bắt đầu dùng thử được ghi vào nhiều chỗ: thư mục state của Javis và
  thư mục ẩn trong tài khoản người dùng (Windows thêm một khoá trong HKCU). Cài lại Javis không reset được.
- Mã kích hoạt là một chuỗi do anh ký bằng khoá bí mật Ed25519 (công cụ mrbright/cap-ma.py). Trong mã có:
  mã máy, hạn dùng (0 = vĩnh viễn), tên khách. Javis chỉ giữ KHOÁ CÔNG KHAI, nên không tự tạo được mã.
- Hết hạn (dùng thử hoặc mã) thì Javis khởi động ở CHẾ ĐỘ KHOÁ: chỉ có màn hình khoá + ô nhập mã. Không nạp
  main.py, nên bot Zalo/Telegram, việc nền, lịch nhắc... đều KHÔNG chạy.
- Đang chạy mà tới hạn: luồng canh tự khởi động lại server, server mới lên ở chế độ khoá.
- Đồng hồ máy bị lùi quá 1 ngày so với lần thấy gần nhất thì coi như hết hạn (chống chỉnh giờ).

GIỚI HẠN (nói thật): đây là mã Python mở trên máy khách. Người rành kỹ thuật vẫn sửa code để bỏ khoá được. Khoá
này chặn người dùng bình thường, không chống được người cố tình bẻ khoá.

Hai điểm nối vào Javis gốc (mrbright/apply.py tự chèn):
  - đầu server/main.py:  import ban_quyen as _mrb_ban_quyen; _mrb_ban_quyen.chan_neu_khoa()
  - cuối server/main.py: _mrb_ban_quyen.gan_vao(app)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# ----------------------------------------------------------------- cấu hình (apply.py ghi từ brand.json)
PUBLIC_KEY_B64 = "HvvJX1z1HzYUOdD7I4b6ndkDFJ-tjIrtI-hhMXoGUOI"
TEN_SAN_PHAM = "Javis"
LIEN_HE = ""
SO_NGAY_DUNG_THU = 7

TIEN_TO_MA = "JMB1"
DUNG_SAI_LUI_GIO = 86400          # đồng hồ lùi quá 1 ngày = gian lận
CHU_KY_CANH = 600                 # luồng canh kiểm lại mỗi 10 phút
_KHOA_CHE = b"jmb-state-v1"       # chỉ để phát hiện sửa tay file trạng thái, KHÔNG phải bí mật

SERVER_DIR = Path(__file__).resolve().parent
APP_DIR = SERVER_DIR.parent
STATE_DIR = Path(os.getenv("JAVIS_STATE_DIR", str(SERVER_DIR)))

_da_chan = False                  # main.py có thể bị nạp 2 lần (python main.py -> uvicorn "main:app")
_da_canh = False
_lock = threading.RLock()


# ----------------------------------------------------------------- mã máy
def _ma_may_tho() -> str:
    """Định danh cố định của máy: Windows MachineGuid, macOS IOPlatformUUID, Linux machine-id."""
    try:
        if sys.platform.startswith("win"):
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0))
            v, _ = winreg.QueryValueEx(k, "MachineGuid")
            if v:
                return "win:" + str(v).strip().lower()
        elif sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True,
                                 text=True, timeout=10).stdout
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return "mac:" + line.split("=")[-1].strip().strip('"').lower()
        else:
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    v = Path(p).read_text().strip()
                    if v:
                        return "linux:" + v.lower()
                except OSError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    import uuid
    return "node:%012x" % uuid.getnode()


_ma_may_cache = ""


def ma_may() -> str:
    """Mã máy hiển thị cho khách gửi anh, dạng XXXX-XXXX-XXXX-XXXX."""
    global _ma_may_cache
    if not _ma_may_cache:
        h = hashlib.sha256(("JMB|" + _ma_may_tho()).encode()).digest()
        s = base64.b32encode(h).decode().rstrip("=")[:16]
        _ma_may_cache = "-".join(s[i:i + 4] for i in range(0, 16, 4))
    return _ma_may_cache


# ----------------------------------------------------------------- nơi lưu trạng thái
def _noi_luu() -> list:
    """Các file giữ ngày bắt đầu dùng thử. Lấy ngày SỚM NHẤT trong các bản còn hợp lệ."""
    ds = [STATE_DIR / ".mrb-state"]
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.getenv("APPDATA") or (home / "AppData" / "Roaming"))
        ds.append(base / ".jmb" / "s.dat")
        ds.append(Path(os.getenv("LOCALAPPDATA") or (home / "AppData" / "Local")) / ".jmb" / "s.dat")
    elif sys.platform == "darwin":
        ds.append(home / "Library" / "Application Support" / ".jmb" / "s.dat")
        ds.append(home / ".config" / ".jmb" / "s.dat")
    else:
        ds.append(home / ".config" / ".jmb" / "s.dat")
        ds.append(home / ".local" / "share" / ".jmb" / "s.dat")
    return ds


def _ma_hoa(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    tag = hmac.new(_KHOA_CHE, raw, hashlib.sha256).hexdigest()[:24]
    return base64.urlsafe_b64encode(raw).decode() + "." + tag


def _giai_ma(s: str):
    try:
        b64, tag = s.strip().split(".", 1)
        raw = base64.urlsafe_b64decode(b64.encode())
        if not hmac.compare_digest(hmac.new(_KHOA_CHE, raw, hashlib.sha256).hexdigest()[:24], tag):
            return None
        d = json.loads(raw)
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _ghi_an_toan(p: Path, text: str) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def _reg_doc():
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\JMBRuntime")
        v, _ = winreg.QueryValueEx(k, "s")
        return str(v)
    except Exception:  # noqa: BLE001
        return None


def _reg_ghi(text: str) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import winreg
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\JMBRuntime")
        winreg.SetValueEx(k, "s", 0, winreg.REG_SZ, text)
    except Exception:  # noqa: BLE001
        pass


def _doc_trang_thai(now: float):
    """Trả (t0, max_thay, gian_lan). Chưa có bản nào thì tạo mới với t0 = now."""
    hop_le, bi_sua = [], False
    nguon = []
    for p in _noi_luu():
        if p.exists():
            try:
                nguon.append(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                bi_sua = True
    r = _reg_doc()
    if r is not None:
        nguon.append(r)
    for s in nguon:
        d = _giai_ma(s)
        if d is None:
            bi_sua = True               # chữ ký không khớp: có người sửa tay file trạng thái
        elif d.get("m") == ma_may() and isinstance(d.get("t0"), (int, float)):
            hop_le.append(d)
        # khác máy (chép thư mục từ máy khác sang): bỏ qua bản đó
    if not hop_le:
        if bi_sua:
            return 0.0, now, True
        return now, now, False
    t0 = min(float(d["t0"]) for d in hop_le)
    mx = max(float(d.get("mx", d["t0"])) for d in hop_le)
    return t0, mx, False


def _luu_trang_thai(t0: float, mx: float) -> None:
    text = _ma_hoa({"m": ma_may(), "t0": int(t0), "mx": int(mx)})
    for p in _noi_luu():
        _ghi_an_toan(p, text)
    _reg_ghi(text)


# ----------------------------------------------------------------- mã kích hoạt
def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def giai_ma_kich_hoat(ma: str):
    """Kiểm chữ ký của mã. Trả (payload, lỗi). Không xét hạn, chỉ xét đúng chữ ký + đúng máy."""
    ma = "".join((ma or "").split())
    try:
        tien_to, p_b64, sig_b64 = ma.split(".")
    except ValueError:
        return None, "Mã kích hoạt không đúng định dạng."
    if tien_to != TIEN_TO_MA:
        return None, "Mã kích hoạt không đúng định dạng."
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub = Ed25519PublicKey.from_public_bytes(_b64d(PUBLIC_KEY_B64))
        pub.verify(_b64d(sig_b64), (tien_to + "." + p_b64).encode())
        d = json.loads(_b64d(p_b64))
    except Exception:  # noqa: BLE001
        return None, "Mã kích hoạt không hợp lệ."
    if d.get("m") != ma_may():
        return None, "Mã kích hoạt này cấp cho máy khác (mã máy không khớp)."
    return d, ""


def _file_ma() -> list:
    ds = [STATE_DIR / "mrb-license.txt"]
    ds += [p.with_name("l.dat") for p in _noi_luu()[1:]]
    return ds


def _doc_ma_da_luu():
    """Mã còn hiệu lực xa nhất trong các bản đã lưu (payload) hoặc None."""
    tot = None
    for p in _file_ma():
        try:
            d, loi = giai_ma_kich_hoat(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        if d and (tot is None or _han(d) > _han(tot)):
            tot = d
    return tot


def _han(d: dict) -> float:
    e = float(d.get("e") or 0)
    return float("inf") if e <= 0 else e


def luu_ma(ma: str):
    """Nhập mã mới. Trả (ok, thông báo)."""
    ma = "".join((ma or "").split())
    d, loi = giai_ma_kich_hoat(ma)
    if not d:
        return False, loi
    now = time.time()
    if _han(d) <= now:
        return False, "Mã kích hoạt này đã hết hạn."
    for p in _file_ma():
        _ghi_an_toan(p, ma)
    with _lock:
        _cache.clear()
    return True, "Đã kích hoạt " + (TEN_SAN_PHAM or "Javis") + ("" if _han(d) == float("inf") else
                                                                  " đến " + _ngay(_han(d))) + "."


def _con_ngay(han: float, now: float) -> int:
    import math
    return max(0, math.ceil((han - now) / 86400))


def _ngay(ts: float) -> str:
    return time.strftime("%d/%m/%Y", time.localtime(ts))


# ----------------------------------------------------------------- trạng thái tổng
_cache: dict = {}


def trang_thai(now: float | None = None) -> dict:
    """{'khoa': bool, 'loai': 'ban_quyen'|'dung_thu'|'khoa', 'ly_do', 'con_ngay', 'het_han', ...}"""
    now = time.time() if now is None else now
    with _lock:
        if _cache.get("t") and now - _cache["t"] < 30:
            return dict(_cache["v"])
        t0, mx, gian_lan = _doc_trang_thai(now)
        lui_gio = now < mx - DUNG_SAI_LUI_GIO
        if not lui_gio and not gian_lan:
            _luu_trang_thai(t0, max(mx, now))
        ma = _doc_ma_da_luu()
        v = {"ma_may": ma_may(), "ten_san_pham": TEN_SAN_PHAM, "lien_he": LIEN_HE,
             "bat_dau_dung_thu": int(t0), "khach": "", "het_han": None}
        het_thu = t0 + SO_NGAY_DUNG_THU * 86400
        if lui_gio:
            v.update(khoa=True, loai="khoa", ly_do="Đồng hồ máy đang chậm hơn thực tế. Hãy chỉnh lại giờ máy cho đúng.")
        elif ma and _han(ma) > now:
            h = _han(ma)
            v.update(khoa=False, loai="ban_quyen", ly_do="", khach=str(ma.get("n") or ""),
                     het_han=None if h == float("inf") else int(h),
                     con_ngay=None if h == float("inf") else _con_ngay(h, now))
        elif gian_lan:
            v.update(khoa=True, loai="khoa", ly_do="Dữ liệu dùng thử không hợp lệ. Vui lòng liên hệ để được kích hoạt.")
        elif now < het_thu:
            v.update(khoa=False, loai="dung_thu", ly_do="", het_han=int(het_thu),
                     con_ngay=_con_ngay(het_thu, now))
        elif ma:
            v.update(khoa=True, loai="khoa", ly_do="Mã kích hoạt đã hết hạn ngày " + _ngay(_han(ma)) + ".",
                     khach=str(ma.get("n") or ""))
        else:
            v.update(khoa=True, loai="khoa", ly_do="Đã hết " + str(SO_NGAY_DUNG_THU) + " ngày dùng thử.")
        _cache.update(t=now, v=v)
        return dict(v)


# ----------------------------------------------------------------- cổng, khởi động lại
def _cong():
    """Host/port giống hệt server Javis sẽ dùng: biến môi trường, rồi .env, rồi tham số --host/--port."""
    env = {}
    try:
        from dotenv import dotenv_values
        env = dict(dotenv_values(APP_DIR / ".env"))
    except Exception:  # noqa: BLE001
        pass
    host = os.getenv("JAVIS_HOST") or env.get("JAVIS_HOST") or "127.0.0.1"
    port = os.getenv("JAVIS_PORT") or env.get("JAVIS_PORT") or "7777"
    argv = list(getattr(sys, "orig_argv", sys.argv))
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            port = argv[i + 1]
        elif a.startswith("--port="):
            port = a.split("=", 1)[1]
        elif a == "--host" and i + 1 < len(argv):
            host = argv[i + 1]
        elif a.startswith("--host="):
            host = a.split("=", 1)[1]
    try:
        return host, int(port)
    except ValueError:
        return host, 7777


def _lenh_goc() -> list:
    argv = list(getattr(sys, "orig_argv", sys.argv))
    return [sys.executable] + argv[1:]


def _hen_khoi_dong_lai() -> None:
    """Chạy một tiến trình phụ: chờ cổng rảnh rồi chạy lại đúng lệnh đã bật server này."""
    host, port = _cong()
    log = SERVER_DIR / "javis.log"
    cmd = [sys.executable, str(Path(__file__).resolve()), "--relaunch", host, str(port), os.getcwd(),
           json.dumps(_lenh_goc()), str(log)]
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "close_fds": True}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)


def _cho_va_chay_lai(host: str, port: int, cwd: str, cmd: list, log: str) -> None:
    h = "127.0.0.1" if host in ("0.0.0.0", "", "::") else host
    het = time.time() + 120
    while time.time() < het:
        try:
            with socket.create_connection((h, port), timeout=1):
                pass
            time.sleep(1)
        except OSError:
            break
    time.sleep(2)
    kw = {"cwd": cwd, "stdin": subprocess.DEVNULL, "close_fds": True}
    f = open(log, "ab")
    kw["stdout"] = f
    kw["stderr"] = subprocess.STDOUT
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)


def _tu_tat_server() -> None:
    """Tắt server đang chạy một cách êm (uvicorn bắt SIGINT/SIGTERM và chạy các bước shutdown)."""
    import signal
    try:
        if sys.platform.startswith("win"):
            signal.raise_signal(signal.SIGINT)
        else:
            os.kill(os.getpid(), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    # Lưới an toàn: 60 giây sau vẫn chưa tắt thì tắt cứng.
    t = threading.Timer(60, lambda: os._exit(0))
    t.daemon = True
    t.start()


def _canh() -> None:
    while True:
        try:
            v = trang_thai()
            cho = CHU_KY_CANH
            if not v["khoa"] and v.get("het_han"):
                cho = max(5, min(CHU_KY_CANH, v["het_han"] - time.time() + 5))
            if v["khoa"]:
                print("[mrb] Hết hạn sử dụng, khởi động lại vào chế độ khoá.", flush=True)
                _hen_khoi_dong_lai()
                _tu_tat_server()
                return
        except Exception as e:  # noqa: BLE001
            print("[mrb] lỗi kiểm tra bản quyền:", e, flush=True)
            cho = CHU_KY_CANH
        time.sleep(cho)
        with _lock:
            _cache.clear()


# ----------------------------------------------------------------- trang khoá / kích hoạt
def trang_html(v: dict, che_do_khoa: bool) -> str:
    e = html.escape
    ten = e(v.get("ten_san_pham") or "Javis")
    if che_do_khoa:
        tieu_de, mo_ta = ten + " đang bị khoá", e(v.get("ly_do") or "")
    elif v.get("loai") == "dung_thu":
        tieu_de = ten + " - bản dùng thử"
        mo_ta = "Còn %s ngày dùng thử (đến %s)." % (v.get("con_ngay"), _ngay(v["het_han"]))
    else:
        tieu_de = ten + " - đã kích hoạt"
        mo_ta = ("Bản quyền vĩnh viễn." if not v.get("het_han")
                 else "Bản quyền còn %s ngày (đến %s)." % (v.get("con_ngay"), _ngay(v["het_han"])))
        if v.get("khach"):
            mo_ta += " Khách hàng: " + e(v["khach"]) + "."
    lien_he = e(v.get("lien_he") or "")
    return """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%(ten)s - Kích hoạt</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1115;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#e8e8ea}
.card{width:min(520px,92vw);background:#181b22;border:1px solid #2a2e38;border-radius:16px;padding:28px}
h1{font-size:20px;margin:0 0 8px} p{color:#b6b9c2;line-height:1.5;margin:6px 0}
.mm{display:flex;gap:8px;align-items:center;margin:16px 0;background:#0f1115;border:1px solid #2a2e38;
border-radius:10px;padding:10px 12px;font:600 17px ui-monospace,Menlo,Consolas,monospace;letter-spacing:1px}
.mm span{flex:1} button{cursor:pointer;border:0;border-radius:10px;padding:10px 14px;font-weight:600}
.copy{background:#2a2e38;color:#e8e8ea;padding:6px 10px;font-size:13px}
textarea{width:100%%;box-sizing:border-box;min-height:84px;background:#0f1115;color:#e8e8ea;border:1px solid #2a2e38;
border-radius:10px;padding:10px;font:13px ui-monospace,Menlo,Consolas,monospace}
.go{background:#4f7cff;color:#fff;width:100%%;margin-top:10px;font-size:15px}
.msg{margin-top:12px;min-height:20px} .ok{color:#5fd38d} .err{color:#ff7b7b}
a{color:#8fb0ff}
</style></head><body><div class="card">
<h1>%(tieu_de)s</h1><p>%(mo_ta)s</p>
<p>Gửi <b>mã máy</b> dưới đây cho nhà cung cấp để nhận mã kích hoạt.%(lh)s</p>
<div class="mm"><span id="mm">%(ma_may)s</span><button class="copy" onclick="navigator.clipboard&&navigator.clipboard.writeText(document.getElementById('mm').textContent);this.textContent='Đã chép'">Chép</button></div>
<textarea id="ma" placeholder="Dán mã kích hoạt vào đây (bắt đầu bằng JMB1.)"></textarea>
<button class="go" id="go">Kích hoạt</button><div class="msg" id="msg"></div>
%(back)s
</div><script>
document.getElementById('go').onclick=async function(){var m=document.getElementById('msg');m.className='msg';
m.textContent='Đang kiểm tra...';try{var r=await fetch('/mrb/kich-hoat',{method:'POST',credentials:'same-origin',
headers:{'Content-Type':'application/json'},body:JSON.stringify({ma:document.getElementById('ma').value})});
var d=await r.json();m.className='msg '+(d.ok?'ok':'err');m.textContent=d.thong_bao||d.error||'Lỗi';
if(d.ok){setTimeout(function(){location.href='/'},%(cho)d)}}catch(e){m.className='msg err';m.textContent='Không gửi được: '+e}};
</script></body></html>""" % {
        "ten": ten, "tieu_de": tieu_de, "mo_ta": mo_ta, "ma_may": e(v.get("ma_may") or ""),
        "lh": (" Liên hệ: <b>" + lien_he + "</b>") if lien_he else "",
        "back": "" if che_do_khoa else '<p style="margin-top:14px"><a href="/">&larr; Quay lại Javis</a></p>',
        "cho": 12000 if che_do_khoa else 1500,
    }


def _app_khoa():
    from fastapi import FastAPI, Body
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="Javis - locked", docs_url=None, redoc_url=None, openapi_url=None)
    trang_thai_server = {"server": None}

    @app.get("/health")
    async def health():
        return {"ok": True, "locked": True}

    @app.get("/mrb/trang-thai")
    async def tt():
        return trang_thai()

    @app.post("/mrb/kich-hoat")
    async def kich_hoat(body: dict = Body(...)):
        ok, tb = luu_ma(str((body or {}).get("ma") or ""))
        if ok and not trang_thai()["khoa"]:
            def _xong():
                time.sleep(0.5)
                _hen_khoi_dong_lai()
                s = trang_thai_server["server"]
                if s is not None:
                    s.should_exit = True
            threading.Thread(target=_xong, daemon=True).start()
            tb += " Đang khởi động lại, chờ khoảng 10 giây..."
        return {"ok": ok, "thong_bao": tb}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def moi_duong(path: str):
        if path.startswith(("api/", "ws", "auth/")) or not path == "" and "." in path.rsplit("/", 1)[-1]:
            return JSONResponse({"error": "locked", "locked": True, **trang_thai()}, status_code=423)
        return HTMLResponse(trang_html(trang_thai(), True))

    return app, trang_thai_server


def _chay_che_do_khoa() -> None:
    import uvicorn
    host, port = _cong()
    app, holder = _app_khoa()
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    holder["server"] = server
    print("[mrb] %s đang bị khoá. Mở http://127.0.0.1:%d để nhập mã kích hoạt. Mã máy: %s"
          % (TEN_SAN_PHAM or "Javis", port, ma_may()), flush=True)
    # Chạy ở luồng riêng: khi bật bằng `uvicorn main:app`, file main.py được nạp BÊN TRONG event loop của
    # uvicorn ngoài, gọi asyncio.run thẳng ở đây sẽ lỗi.
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    t.join()
    os._exit(0)


# ----------------------------------------------------------------- hai điểm nối
def chan_neu_khoa() -> None:
    """Gọi ở ĐẦU main.py. Hết hạn thì chạy trang khoá và KHÔNG BAO GIỜ trả về (Javis không được nạp)."""
    global _da_chan, _da_canh
    if _da_chan:
        return
    _da_chan = True
    v = trang_thai()
    if v["khoa"]:
        _chay_che_do_khoa()
    if not _da_canh:
        _da_canh = True
        threading.Thread(target=_canh, name="mrb-canh", daemon=True).start()


def gan_vao(app) -> None:
    """Gọi ở CUỐI main.py: trang /mrb + API trạng thái/kích hoạt (sau cổng đăng nhập của Javis)."""
    from fastapi import Body
    from fastapi.responses import HTMLResponse

    @app.get("/mrb", response_class=HTMLResponse)
    async def mrb_trang():
        return HTMLResponse(trang_html(trang_thai(), False))

    @app.get("/mrb/trang-thai")
    async def mrb_tt():
        return trang_thai()

    @app.post("/mrb/kich-hoat")
    async def mrb_kich_hoat(body: dict = Body(...)):
        ok, tb = luu_ma(str((body or {}).get("ma") or ""))
        return {"ok": ok, "thong_bao": tb}


if __name__ == "__main__":
    if len(sys.argv) >= 7 and sys.argv[1] == "--relaunch":
        _cho_va_chay_lai(sys.argv[2], int(sys.argv[3]), sys.argv[4], json.loads(sys.argv[5]), sys.argv[6])
    elif len(sys.argv) >= 2 and sys.argv[1] == "--ma-may":
        print(ma_may())
    elif len(sys.argv) >= 2 and sys.argv[1] == "--trang-thai":
        print(json.dumps(trang_thai(), ensure_ascii=False, indent=2))
