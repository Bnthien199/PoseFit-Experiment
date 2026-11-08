# Checklist cài và mở trên máy thành viên

Ngày 2026-11-08 · Asia/Bangkok. 09H.2 kiểm định source 09H.1 build5, không đổi mã runtime.

Đây là checklist CHƯA THỰC HIỆN trên máy vật lý thứ hai. Người kiểm ghi ngày, Windows/Python, kết quả và thông báo lỗi; không đánh dấu hoàn tất trước khi thử thật. Chưa được thu dữ liệu người thật chỉ vì cài thành công.

1. Lấy địa chỉ repo source do trưởng nhóm cung cấp. Clone lần đầu, hoặc đóng app rồi pull bản nhóm đã ghim. Không clone/public push nguyên dataset nghiên cứu. Có thể dùng source ZIP đi kèm nếu nhóm chưa phát repo; đó chưa phải thử GitHub clone từ xa.
2. Cần Windows, Python 3.11 kèm py launcher, mạng để cài dependencies và quyền ghi thư mục ngắn, ví dụ C:\PoseFit. Không cần ổ F:, model hoặc các run cũ. Không dùng thư mục bảo vệ chỉ đọc.
3. Mở thư mục recorder, nhấp đôi Cai_dat.cmd. Chờ báo cài/preflight thành công. Không tự sửa versions, manifest hoặc trusted.py để bỏ lỗi. Cài trên một máy thứ hai vẫn cần người kiểm thực hiện, dù cùng máy dev đã cài fresh virtualenv PASS.
4. Nhấp đôi Mo_PoseFit.vbs. Kiểm một cửa sổ tiếng Việt, bốn hoạt động, góc/kịch bản/tay; chữ không vuông, nút chính nhìn thấy ở màn hình laptop. Startup không mở camera hoặc ghi hình. Ghi nhận nếu antivirus/WSH hoặc quyền chạy script cản; không tắt bảo mật để vượt lỗi.
5. Đọc banner chưa phê duyệt thu thập. Chỉ sau người phụ trách cho phép pilot, kiểm đúng webcam/quyền/preview, không chạy app camera thứ hai. Dừng nếu có lỗi.
6. Sau test được phép, xuất ZIP, tự chuyển sang máy nhận, đối chiếu SHA256 và giải nén/verify. Ghi rõ kênh chuyển, kích thước, hash trước/sau, số video; không kết luận Zalo đã kiểm nếu chỉ copy local.

Trưởng nhóm cung cấp URL/commit thật của repo khi phân phối. H2 chỉ tạo local fixture repo, không tạo remote hoặc push. Dữ liệu cá nhân, video, ZIP, venv, cache/log luôn nằm ngoài source tracked.


