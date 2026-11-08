# Checklist pilot một người có giám sát

Ngày 2026-11-08 · Asia/Bangkok. 09H.2 kiểm định source 09H.1 build5, không đổi mã runtime.

**PENDING — không phải giấy phép thu hình.** Các ô dưới đây dành cho người phụ trách thực hiện và ghi bằng chứng; H2 không tự đánh dấu đã hoàn tất.

- [ ] Reviewer xem G7/H1 mtime exception, hash/content và hạn chế evidence, ghi quyết định chấp nhận hoặc yêu cầu xử lý thêm. Không đổi timestamp để buộc PASS.
- [ ] Người phụ trách phê duyệt pilot giới hạn: một người, thiết bị, thư mục giữ dữ liệu, người nhận, thời hạn và cách rút consent/xử lý dữ liệu. Không suy quyền thu hình từ test PASS.
- [ ] Người tham gia đọc và xác nhận consent thật cho local recording/chia sẻ nhóm; dùng mã giả danh, biết quyền dừng/từ chối. Không dùng simulated consent từ fixture.
- [ ] Trên máy thực tế, chạy checklist cài/GUI; kiểm đúng camera và một owner. Thực hiện test kỹ thuật được người dùng chủ động bắt đầu, ưu tiên không cần bài tập.
- [ ] Kiểm countdown/no early frames, stop/save/decode/timestamps/tick; đóng/mở lại giữ tiến độ. Không coi tick là động tác đúng.
- [ ] Xuất ZIP, xem inventory, chọn thư mục; tự chuyển sang máy nhận/kênh được phép và so SHA256/giải nén. Không dùng local copy H2 để thay bằng chứng cross-device/Zalo.
- [ ] Ghi log pilot, lỗi, dữ liệu cần quay lại, quyền giữ/chia sẻ. Người phụ trách human review footage trước dùng vào nghiên cứu; app không gán GT.

Thu thập chính thức toàn nhóm cần phê duyệt riêng và protocol/release checks phù hợp. Pilot một người không tự chứng minh robustness, participant independence, rep-event GT hoặc Plank accuracy. H2 chưa làm physical pilot hay formal collection.


