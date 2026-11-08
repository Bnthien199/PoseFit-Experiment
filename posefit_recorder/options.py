"""Stable machine IDs and Vietnamese participant instructions."""
OPTIONS = {
    'standing': ('Đứng', [('natural', 'Đứng tự nhiên.'), ('crossed', 'Khoanh tay.'),
                           ('raised', 'Giơ hai tay.'), ('hips', 'Đặt tay lên hông.')]),
    'squat': ('Squat', [('complete5', '5 lần hoàn chỉnh.'), ('partial5', '5 lần chưa hoàn chỉnh.'),
                         ('standing0', 'Đứng thẳng, không Squat.')]),
    'pushup': ('Chống đẩy', [('complete5', '5 lần hoàn chỉnh.'), ('partial5', '5 lần chưa hoàn chỉnh.'),
                            ('hold0', 'Giữ tư thế chống tay, không thực hiện lần hoàn chỉnh.')]),
    'plank': ('Plank', [('hold15', 'Giữ 15 giây.'), ('hold20', 'Giữ 20 giây.'),
                        ('hold30', 'Giữ 30 giây.'), ('interrupted', 'Giữ rồi ngắt quãng.')]),
}
ANGLES = {0: 'Chính diện 0°', 45: 'Góc 45°', 90: 'Nghiêng 90°'}
CONSENT = ('Tôi đồng ý ghi hình cục bộ và tự chia sẻ video với nhóm nghiên cứu. '
           'Tôi có thể từ chối hoặc dừng quay bất cứ lúc nào.')
PARENT_NOTICE = 'Bản kiểm thử — chưa được phê duyệt thu thập dữ liệu chính thức.'


def instruction(exercise, scenario):
    text = dict(OPTIONS[exercise][1])[scenario]
    if exercise == 'standing':
        text += ' Giữ tư thế đã chọn khoảng 10 giây.'
    return text + ' Đảm bảo cơ thể nằm trong khung hình. Chỉ làm trong khả năng thoải mái; dừng nếu đau hoặc mệt.'


def declaration(exercise, scenario, angle):
    if exercise not in OPTIONS or scenario not in dict(OPTIONS[exercise][1]) or angle not in ANGLES:
        raise ValueError('Hoạt động, kịch bản hoặc góc quay không hợp lệ.')
    return dict(exercise_id=exercise, instructed_scenario_id=scenario,
                declared_camera_angle=angle,
                standing_posture=scenario if exercise == 'standing' else None,
                instruction_text=instruction(exercise, scenario),
                instruction_is_ground_truth=False, angle_independently_verified=False,
                machine_predictions=None, human_ground_truth=None, human_review_status='UNREVIEWED')
