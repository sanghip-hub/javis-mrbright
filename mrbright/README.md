# Javis Mr Bright: gói Javis OS cài cho khách

Thư mục này nằm trong repo `sanghip-hub/javis-mrbright`. Repo đó là bản Javis OS gốc (github.com/blogminhquy/javis-os, giấy phép MIT) cộng thêm phần tuỳ biến của anh. Mọi chỗ sửa đều do `apply.py` làm lại, nên lấy bản gốc mới về lúc nào cũng được.

## Có gì khác bản gốc

| Thay đổi | File |
|---|---|
| Bỏ lời mời "Tặng sao" và dòng "by Javis Foundation" | `dashboard/index.html` |
| Dùng thử 7 ngày. Hết hạn thì khoá cả Javis, kể cả bot Zalo/Telegram và việc nền | `server/ban_quyen.py` + 2 dòng nối trong `server/main.py` |
| Mã kích hoạt gắn từng máy, có hạn hoặc vĩnh viễn, ký bằng khoá của anh | `cap-ma.py` (chỉ chạy trên máy anh) |
| Thanh báo "còn N ngày" và trang `/mrb` để nhập mã | `dashboard/mrb-banner.js` |
| Nút Cập nhật trong app kéo code từ repo của anh, không phải repo gốc | `server/updater.py`, `GITHUB_REPO` trong `server/main.py` |
| Không hiện thông báo của repo gốc | `ANNOUNCEMENTS.json` |
| Bộ cài 1 cú bấm cho Windows và Mac, chạy online hoặc từ file ZIP | `install/`, `build-zip.sh` |

File `LICENSE` của bản gốc được giữ nguyên. Giấy phép MIT bắt buộc giữ file này.

## Cài cho khách

**Cách 1: qua mạng.** Không cần gửi file, khách dán một dòng lệnh:
- Windows (PowerShell): `irm https://raw.githubusercontent.com/sanghip-hub/javis-mrbright/main/mrbright/install/cai-windows.ps1 | iex`
- Mac (Terminal): `curl -fsSL https://raw.githubusercontent.com/sanghip-hub/javis-mrbright/main/mrbright/install/cai-mac.sh | bash`

**Cách 2: file ZIP.** Chạy `bash mrbright/build-zip.sh` để ra file `dist/JavisMrBright-<phiên bản>.zip`, rồi gửi cho khách.
- Windows: giải nén, bấm đúp `CAI-DAT-WINDOWS.bat`.
- Mac: giải nén, chuột phải vào `CAI-DAT-MAC.command`, chọn Open.

Cả hai cách đều cài vào `~/JavisOS` (Windows là `%USERPROFILE%\JavisOS`) và cần Internet để tải Python, Node và thư viện. Cài xong có biểu tượng "Javis" trên Desktop.

## Cấp mã kích hoạt

1. Khách mở Javis (trang khoá hiện ra khi đã hết hạn), hoặc vào `http://127.0.0.1:7777/mrb`, rồi gửi anh **mã máy** dạng `ABCD-EFGH-IJKL-MNOP`.
2. Trên máy anh chạy một trong các lệnh:
   ```
   python3 mrbright/cap-ma.py cap --may ABCD-EFGH-IJKL-MNOP --ngay 30 --ten "Công ty A"
   python3 mrbright/cap-ma.py cap --may ABCD-EFGH-IJKL-MNOP --den 2027-12-31 --ten "Công ty A"
   python3 mrbright/cap-ma.py cap --may ABCD-EFGH-IJKL-MNOP --vinh-vien --ten "Công ty A"
   ```
3. Gửi khách chuỗi `JMB1....` vừa in ra. Khách dán vào ô, bấm Kích hoạt, Javis tự khởi động lại.
4. Gia hạn thì cấp mã mới cho cùng mã máy. Mỗi lần cấp đều được ghi vào `~/.javis-mrbright/so-cap-ma.csv`.

**Khoá bí mật** nằm ở `~/.javis-mrbright/khoa-bi-mat.pem`, chỉ có trên máy anh.
- Mất file này thì không cấp được mã cho khách đã cài, nên hãy sao lưu nó.
- Lộ file này thì ai cũng tự cấp mã được, nên không đưa vào git và không gửi qua Zalo.

## Cập nhật theo bản gốc

```
bash mrbright/sync-upstream.sh          # kéo bản gốc, áp lại tuỳ biến, kiểm tra, commit
# chạy thử trên máy anh, ổn thì:
git push                                # máy khách bấm Cập nhật là nhận bản mới
```
Nếu bản gốc đổi cấu trúc đúng chỗ mình sửa, script sẽ dừng và báo chỗ nào. Lúc đó sửa `apply.py` cho khớp rồi chạy lại.

## Giới hạn cần biết

- Javis là mã Python mở chạy trên máy khách. Người rành kỹ thuật vẫn sửa code để bỏ khoá được. Khoá này chặn người dùng bình thường, không chống được người cố tình bẻ khoá.
- Khách xoá hết các file trạng thái ẩn (`server/.mrb-state`, `.jmb` trong thư mục người dùng, và trên Windows cả khoá registry `HKCU\Software\JMBRuntime`) thì được dùng thử lại từ đầu. Làm vậy cần biết chính xác các chỗ đó.
- Lùi đồng hồ máy quá 1 ngày thì Javis khoá cho tới khi chỉnh giờ lại đúng.
- Mã máy đổi khi cài lại Windows hoặc thay bo mạch chủ. Khi đó anh cấp mã mới cho mã máy mới.
- Docker: mã máy lấy từ `/etc/machine-id` của container, có thể đổi khi tạo lại container. Gói này nhắm tới máy Windows và Mac.
