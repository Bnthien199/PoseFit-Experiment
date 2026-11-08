# PoseFit — Thực nghiệm

Ứng dụng Windows giúp thành viên quay video theo nội dung được giao, kiểm tra tệp đã lưu và xuất ZIP để tự gửi cho nhóm. Một cửa sổ tiếng Việt, không cần lập trình hoặc sửa JSON khi sử dụng.

> Đây là bản recorder đã kiểm thử kỹ thuật. Thu thập dữ liệu người thật chính thức **chưa được phê duyệt**. Chỉ ghi hình sau khi người phụ trách cho phép pilot/thu thập phù hợp và người tham gia đồng ý.

## 1. Giới thiệu và cách nhận nhiệm vụ

Trưởng nhóm giao hoạt động riêng qua Zalo. Chỉ quay nội dung được giao; **không cần hoàn thành cả bốn hoạt động**. Ứng dụng không có quản lý phân công hoặc giao diện trưởng nhóm, không tự gửi dữ liệu.

## 2. Yêu cầu máy tính

- Windows, webcam và thư mục có quyền ghi.
- Python **3.11**, có **Python Launcher (`py`)**. Khi cài Python, chọn thành phần launcher nếu được hỏi.
- Internet cho lần cài thư viện đầu tiên. Các lần quay/lưu/xuất sau đó hoạt động cục bộ.

Các phiên bản thư viện được ghi cố định trong `requirements.txt`. Recorder không chạy inference khi capture, không cần model, MediaPipe hoặc các thư mục nghiên cứu cũ.

## 3. Tải phần mềm từ GitHub

Cách dễ nhất: mở [PoseFit-Experiment](https://github.com/Bnthien199/PoseFit-Experiment), chọn **Code → Download ZIP**, rồi giải nén.

Nếu đã dùng Git, có thể tải bằng:

```powershell
git clone https://github.com/Bnthien199/PoseFit-Experiment.git C:\PoseFit
```

Khi cập nhật bằng Git, đóng ứng dụng trước rồi chạy `git pull --ff-only` trong thư mục đã clone. Thành viên chỉ tải source; không push video hoặc dữ liệu thực nghiệm.

## 4. Giải nén vào đường dẫn ngắn

Ví dụ `C:\PoseFit`, hoặc một thư mục ngắn khác có quyền ghi. Mở đúng thư mục chứa **Cai_dat.cmd**, **Mo_PoseFit.vbs** và **launch.py**; không chạy trực tiếp bên trong tệp ZIP. Nếu Download ZIP tạo thêm thư mục ngoài, mở thư mục ứng dụng bên trong.

## 5. Cài đặt lần đầu

Nhấp đôi **Cai_dat.cmd**, chờ tải thư viện và kiểm tra môi trường. Chỉ tiếp tục khi có thông báo cài đặt/kiểm tra thành công. Script tạo `.venv` riêng cạnh ứng dụng; không yêu cầu cài model hoặc sao chép thư mục từ máy trưởng nhóm.

Nếu cài lỗi, giữ nội dung thông báo và gửi người phụ trách kỹ thuật. Không tự đổi phiên bản trong requirements hoặc sửa manifest để bỏ qua kiểm tra.

## 6. Mở ứng dụng

Nhấp đôi **Mo_PoseFit.vbs**. Cửa sổ có tiêu đề **PoseFit — Thực nghiệm**. Mỗi lần mở không tự mở camera và không tự ghi hình. Sau khi cài xong, các thao tác hằng ngày không cần terminal.

## 7. Nhập mã người tham gia

Nhập mã do nhóm cấp, ví dụ **P001**, rồi bấm sang ô khác. Chỉ dùng chữ, số, `_` hoặc `-`, bắt đầu bằng chữ, tối đa 32 ký tự. Không nhập tên thật, số điện thoại hoặc email. Mã được giữ khi mở lại ứng dụng.

## 8. Xác nhận đồng ý ghi hình

Đọc hướng dẫn và chọn **Tôi đồng ý ghi hình và chia sẻ với nhóm** khi thực sự đồng ý. Có thể từ chối hoặc dừng bất cứ lúc nào. Ô đồng ý không tự được tích lại sau khi khởi động lại; checkbox không thay thế phê duyệt pilot/thu thập của người phụ trách.

## 9. Chọn hoạt động

Bấm một trong bốn thẻ: **Đứng**, **Squat**, **Chống đẩy**, **Plank**. Chọn đúng hoạt động được giao; thứ tự tùy ý.

## 10. Chọn kịch bản, góc và tư thế tay

- **Đứng:** tự nhiên, khoanh tay, giơ hai tay hoặc tay lên hông; góc 0°/45°/90°. Gợi ý giữ khoảng 10 giây.
- **Squat:** 5 lần hoàn chỉnh, 5 lần chưa hoàn chỉnh hoặc đứng không Squat.
- **Chống đẩy:** 5 lần hoàn chỉnh, 5 lần chưa hoàn chỉnh hoặc giữ chống tay không thực hiện lần hoàn chỉnh.
- **Plank:** mục tiêu 15/20/30 giây hoặc giữ rồi ngắt quãng.

Mọi hoạt động có góc 0°/45°/90°. Có thể cuộn bảng lựa chọn bên phải nếu màn hình thấp. Số lần/thời lượng chỉ là hướng dẫn; góc là khai báo, chưa phải nhãn Ground Truth được người duyệt. Chỉ thực hiện trong khả năng thoải mái và dừng nếu đau hoặc mệt.

## 11. Mở camera và bắt đầu quay

Bấm **Mở camera**, kiểm tra cơ thể trong khung hình. Nếu sai nguồn, đóng camera rồi dùng **Chọn camera**. Không mở thêm ứng dụng khác dùng cùng webcam.

Khi đã nhập mã, đồng ý và có preview, bấm **Bắt đầu quay**. Ứng dụng kiểm điều kiện lưu và chuẩn bị bộ ghi trước countdown.

## 12. Chờ 3–2–1

Chờ đủ **3 → 2 → 1 → BẮT ĐẦU!** và trạng thái **ĐANG GHI HÌNH**. Video chỉ bắt đầu sau countdown, từ frame hợp lệ đầu tiên. Có thể hủy trong countdown. Video gốc không chứa chữ của giao diện/countdown hoặc audio.

## 13. Dừng và lưu video

Bấm **Dừng và lưu video**, rồi chờ **Đang kiểm tra và lưu video...**. Ứng dụng đóng writer, kiểm khả năng giải mã, timestamps, metadata và SHA256 trước khi báo thành công. Đồng hồ là timeline ghi hình, không xác nhận thời gian giữ Plank đúng tư thế.

## 14. Kiểm tra tick xanh

Chỉ **Đã lưu video thành công!** và dấu **✓** mới xác nhận tệp đã được kiểm tra. Tick xanh **không xác nhận động tác chính xác, đủ số rep, đủ thời lượng hoặc đã hoàn thành mọi việc được giao**. Mở lại ứng dụng sẽ kiểm lại dữ liệu; tệp bị sửa hoặc thiếu có thể mất tick.

## 15. Quay thêm nội dung

Chọn hoạt động/kịch bản/góc tiếp theo rồi bắt đầu một lượt mới. Camera, mã và tiến độ được giữ sau khi lưu; app không tự quay lượt kế tiếp. Quay cùng một nội dung nhiều lần vẫn giữ các take riêng, không ghi đè video cũ.

## 16. Chọn thư mục xuất ZIP

Chỉ cần **một video hợp lệ** đã có thể bấm **Xuất dữ liệu ZIP**. Xem danh sách và số lượt; tự đối chiếu nhiệm vụ nhận qua Zalo. Xác nhận rồi chọn thư mục bằng hộp thoại Windows và bấm **Lưu ZIP tại đây**.

Ứng dụng kiểm ZIP trước khi báo thành công; tệp trùng tên nhận hậu tố, không thay tệp cũ. Dữ liệu nguồn không bị xóa sau khi xuất.

## 17. Tìm ZIP và gửi cho trưởng nhóm

Khi hiện **Đã xuất dữ liệu thành công!**, xem tên, thư mục, dung lượng và số video. Bấm **Mở thư mục chứa ZIP**. Tên thường có dạng `PoseFit_P001_<ngày_giờ>.zip`.

Thành viên **tự gửi ZIP qua kênh riêng được nhóm phê duyệt**, chẳng hạn Zalo theo hướng dẫn của trưởng nhóm. Ứng dụng không tự upload GitHub hoặc Zalo. Không gửi ZIP qua mục Issues hay đính kèm vào repo public này.

## 18. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không tìm thấy Python/`py` khi cài | Kiểm tra Python 3.11 và Python Launcher, sau đó chạy lại Cai_dat.cmd. |
| Không mở được app hoặc sai thư viện | Dùng đúng bộ source đầy đủ và môi trường được Cai_dat.cmd tạo; gửi thông báo lỗi cho người phụ trách. |
| Đường dẫn lưu quá dài | Chuyển bộ ứng dụng sang thư mục ngắn hơn có quyền ghi rồi thử lại. Giữ dữ liệu cũ. |
| Camera không mở, bị chiếm hoặc mất hình | Kiểm tra kết nối/quyền camera Windows, đóng app khác đang dùng webcam, chọn lại nguồn và mở lại. |
| Nút quay chưa bật | Kiểm tra mã, checkbox đồng ý và preview đã có hình. |
| Lưu lỗi hoặc không có tick | Kiểm tra dung lượng/quyền ghi; giữ nguyên dữ liệu, bấm Kiểm tra lại dữ liệu. Lượt hỏng/chưa hoàn tất có thể cần quay lại. |
| Xuất ZIP lỗi | Giữ video nguồn, kiểm tra lại dữ liệu hoặc chọn thư mục đích khác có đủ chỗ rồi thử lại. |

Không sửa metadata/JSON hoặc manifest để tạo tick xanh. Nếu cần hỗ trợ, gửi thông báo lỗi qua kênh riêng; kiểm tra nội dung trước khi chia sẻ nhật ký.

## 19. Quyền riêng tư và phạm vi kiểm chứng

Repo này **public và chỉ dành cho source**. Dữ liệu cục bộ mặc định nằm trong `data/` cạnh ứng dụng. Không đưa video, sessions, consent thực, ZIP xuất, log người dùng, `.venv`, token hoặc mật khẩu lên GitHub. `.gitignore` đã có quy tắc loại các nhóm này.

Bản 09H.2 có 80/80 regression và 104/104 kiểm tra nghiệm thu kỹ thuật PASS trên cùng máy phát triển, gồm local clone/cài mới, quay fixture và ZIP handoff local. Chưa kiểm cài trên máy vật lý thứ hai, chuyển Zalo hoặc native recording người thật. Native folder picker đã có evidence H1; H2 chưa kiểm lại được vì công cụ Windows mất kết nối. Ngoại lệ mtime README lịch sử vẫn mở, nội dung/hash không đổi. Test PASS không tự cấp phép thu thập dữ liệu người thật.

Trước phân phối rộng, người phụ trách thực hiện [checklist cài đặt](INSTALLATION_CHECKLIST_VI.md) và [checklist pilot](PILOT_ACCEPTANCE_CHECKLIST_VI.md). [Hướng dẫn thêm](USER_GUIDE_VI.md) · [Thư viện bên thứ ba](THIRD_PARTY_NOTICES.md).
