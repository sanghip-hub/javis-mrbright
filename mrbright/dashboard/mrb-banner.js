/* mrb-banner.js - Javis Mr Bright: thanh báo còn bao nhiêu ngày dùng thử / bản quyền (server/ban_quyen.py). */
(function () {
  "use strict";
  function ve(d) {
    if (!d || d.khoa) return;
    var sap = d.loai === "dung_thu" || (d.loai === "ban_quyen" && d.con_ngay != null && d.con_ngay <= 7);
    if (!sap || document.getElementById("mrbBar")) return;
    var bar = document.createElement("div");
    bar.id = "mrbBar";
    bar.style.cssText = "position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:99999;" +
      "background:#1f2430;color:#e8e8ea;border:1px solid #3a4152;border-radius:999px;padding:6px 8px 6px 14px;" +
      "font:13px system-ui,-apple-system,'Segoe UI',sans-serif;display:flex;gap:10px;align-items:center;" +
      "box-shadow:0 6px 24px rgba(0,0,0,.35);max-width:92vw";
    var chu = d.loai === "dung_thu" ? "Bản dùng thử: còn " + d.con_ngay + " ngày"
                                    : "Bản quyền còn " + d.con_ngay + " ngày";
    var span = document.createElement("span");
    span.textContent = chu;
    var a = document.createElement("a");
    a.href = "/mrb";
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "Nhập mã kích hoạt";
    a.style.cssText = "background:#4f7cff;color:#fff;border-radius:999px;padding:4px 10px;text-decoration:none;font-weight:600";
    var x = document.createElement("button");
    x.textContent = "×";
    x.title = "Ẩn";
    x.style.cssText = "background:none;border:0;color:#9aa0ad;font-size:16px;cursor:pointer;padding:0 4px";
    x.onclick = function () { bar.remove(); };
    bar.appendChild(span); bar.appendChild(a); bar.appendChild(x);
    document.body.appendChild(bar);
  }
  function nap() {
    fetch("/mrb/trang-thai", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(ve)
      .catch(function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(nap, 1500); });
  else setTimeout(nap, 1500);
  // Trang mở trước khi đăng nhập thì lần đầu bị 401: hỏi lại định kỳ.
  setInterval(nap, 5 * 60 * 1000);
})();
