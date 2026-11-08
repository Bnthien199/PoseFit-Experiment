"""Vietnamese desktop recorder. Qt schedules countdown; camera process owns raw frames."""
from pathlib import Path
import multiprocessing as mp
import queue
import time
import traceback
import uuid
from PySide6 import QtCore, QtGui, QtWidgets
import cv2
from .capture import capture_main
from .storage import Store, read, declaration, check_space, identifier, finalize_take
from .exporter import export_zip
from .options import OPTIONS, ANGLES, CONSENT, PARENT_NOTICE, instruction
from .fonts import configure_font


class Signals(QtCore.QObject):
    done = QtCore.Signal(object, object)


class Job(QtCore.QRunnable):
    def __init__(self, work):
        super().__init__(); self.work = work; self.signals = Signals()
    def run(self):
        try: self.signals.done.emit(self.work(), None)
        except Exception:
            self.signals.done.emit(None, traceback.format_exc())


class Preview(QtWidgets.QWidget):
    def __init__(self):
        super().__init__(); self.image = None; self.countdown = ''; self.setMinimumSize(400, 250)
    def paintEvent(self, event):
        p = QtGui.QPainter(self); p.fillRect(self.rect(), QtGui.QColor('#101e30'))
        if self.image is not None:
            size = self.image.size().scaled(self.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            rect = QtCore.QRect((self.width()-size.width())//2, (self.height()-size.height())//2, size.width(), size.height())
            p.drawImage(rect, self.image)
        else:
            p.setPen(QtGui.QColor('#c0d2e4')); p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, 'Mở camera để xem trước\nChưa có ghi hình')
        if self.countdown:
            p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 110)); p.setPen(QtGui.QColor('white'))
            p.setFont(QtGui.QFont('Segoe UI', 64, QtGui.QFont.Weight.Bold)); p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self.countdown)


class RecorderWindow(QtWidgets.QMainWindow):
    def __init__(self, data_root, release, *, capture_factory=None, test_only=False, countdown_ms=1000):
        super().__init__(); configure_font(QtWidgets.QApplication.instance()); self.store = Store(data_root); self.release = release
        self.lock = QtCore.QLockFile(str(self.store.root / 'application.lock'))
        if not self.lock.tryLock(0):
            raise RuntimeError('Thư mục dữ liệu đang được PoseFit khác sử dụng. Hãy đóng cửa sổ đó trước.')
        self.capture_factory = capture_factory; self.test_only = test_only; self.countdown_ms = countdown_ms
        self.process = None; self.jobs = set(); self.inventory = []; self.session = None; self.busy = False
        self.state = 'IDLE'; self.source = dict(index=0, backend='MSMF'); self.latest = None
        self.clean_exit = False
        self.last_preview = 0.; self.opened_at = 0.; self.close_pending = False; self.camera_close_at = None
        self.selection_generation = 0; self.countdown_values = []; self.last_saved = None; self.last_zip = None
        self.dialog_factory = None; self.confirm_export = None
        self.setWindowTitle('PoseFit — Thực nghiệm'); self.resize(1280, 760); self.setMinimumSize(1000, 650)
        central = QtWidgets.QWidget(); self.setCentralWidget(central); outer = QtWidgets.QVBoxLayout(central); outer.setContentsMargins(22,18,22,18); outer.setSpacing(12)
        header = QtWidgets.QHBoxLayout(); title = QtWidgets.QLabel('PoseFit — Thực nghiệm'); title.setObjectName('title'); header.addWidget(title); header.addStretch()
        self.help_button = QtWidgets.QPushButton('Hướng dẫn'); header.addWidget(self.help_button); outer.addLayout(header)
        notice = QtWidgets.QLabel(PARENT_NOTICE); notice.setObjectName('notice'); notice.setWordWrap(True); outer.addWidget(notice)
        identity = QtWidgets.QHBoxLayout(); identity.addWidget(QtWidgets.QLabel('Mã người tham gia'))
        self.participant = QtWidgets.QLineEdit(); self.participant.setPlaceholderText('Ví dụ: P001'); self.participant.setMaxLength(32); self.participant.setMaximumWidth(190); identity.addWidget(self.participant)
        self.consent = QtWidgets.QCheckBox(CONSENT); self.consent.setToolTip(CONSENT); self.consent.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        # A wrapped label keeps the consent text readable at laptop width.
        self.consent.setText('Tôi đồng ý ghi hình và chia sẻ với nhóm'); identity.addWidget(self.consent, 1); outer.addLayout(identity)
        cards = QtWidgets.QHBoxLayout(); self.activity_group = QtWidgets.QButtonGroup(self); self.activity_buttons = {}
        for key, (label, _) in OPTIONS.items():
            b = QtWidgets.QPushButton(label); b.setCheckable(True); b.setMinimumHeight(56); b.setObjectName('activity'); self.activity_group.addButton(b); self.activity_buttons[key] = b
            b.clicked.connect(lambda checked=False, k=key: self.select_activity(k)); cards.addWidget(b)
        outer.addLayout(cards)
        middle = QtWidgets.QHBoxLayout(); self.preview = Preview(); middle.addWidget(self.preview, 7)
        side = QtWidgets.QVBoxLayout(); side.setSpacing(8)
        self.scenario_label = QtWidgets.QLabel('Tư thế'); side.addWidget(self.scenario_label); self.scenario = QtWidgets.QComboBox(); side.addWidget(self.scenario)
        side.addWidget(QtWidgets.QLabel('Góc quay đã chọn')); self.angle = QtWidgets.QComboBox(); side.addWidget(self.angle)
        self.instruction = QtWidgets.QLabel(); self.instruction.setWordWrap(True); self.instruction.setObjectName('instruction'); side.addWidget(self.instruction)
        explain = QtWidgets.QLabel('Chỉ quay nội dung được giao qua Zalo.\nDấu ✓ xác nhận tệp đã kiểm tra, chưa xác nhận động tác đúng.'); explain.setWordWrap(True); explain.setMinimumHeight(explain.heightForWidth(310)+4); side.addWidget(explain)
        self.progress_title = QtWidgets.QLabel('Các lượt quay của phiên này'); side.addWidget(self.progress_title); self.progress_list = QtWidgets.QListWidget(); self.progress_list.setWordWrap(True); self.progress_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.progress_list.setMinimumHeight(110); side.addWidget(self.progress_list, 1)
        self.refresh_button = QtWidgets.QPushButton('Kiểm tra lại dữ liệu'); side.addWidget(self.refresh_button)
        panel = QtWidgets.QWidget(); panel.setLayout(side); side.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetMinimumSize)
        self.side_scroll = QtWidgets.QScrollArea(); self.side_scroll.setWidgetResizable(True); self.side_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame); self.side_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.side_scroll.setWidget(panel); self.side_scroll.setMinimumWidth(340); self.side_scroll.setMaximumWidth(410); middle.addWidget(self.side_scroll, 3); outer.addLayout(middle, 1)
        self.status = QtWidgets.QLabel('Nhập mã người tham gia, đồng ý ghi hình rồi mở camera.'); self.status.setWordWrap(True); self.status.setObjectName('status'); outer.addWidget(self.status)
        footer = QtWidgets.QHBoxLayout(); self.camera_button = QtWidgets.QPushButton('Mở camera'); self.camera_choice = QtWidgets.QPushButton('Chọn camera'); footer.addWidget(self.camera_button); footer.addWidget(self.camera_choice)
        self.timer_label = QtWidgets.QLabel('00:00.0'); self.timer_label.setObjectName('timer'); footer.addWidget(self.timer_label)
        self.record_button = QtWidgets.QPushButton('Bắt đầu quay'); self.record_button.setMinimumHeight(54); self.record_button.setObjectName('record'); footer.addWidget(self.record_button, 1)
        self.export_button = QtWidgets.QPushButton('Xuất dữ liệu ZIP'); self.export_button.setMinimumHeight(54); footer.addWidget(self.export_button); outer.addLayout(footer)
        self.folder_button = QtWidgets.QPushButton('Mở thư mục chứa ZIP'); self.folder_button.setVisible(False); outer.addWidget(self.folder_button)
        self.setStyleSheet((Path(__file__).with_name('style.qss')).read_text('utf-8'))
        self.participant.editingFinished.connect(self.change_participant); self.consent.toggled.connect(self.sync)
        self.scenario.currentIndexChanged.connect(self.update_instruction); self.angle.currentIndexChanged.connect(self.sync)
        self.camera_button.clicked.connect(self.toggle_camera); self.camera_choice.clicked.connect(self.choose_camera)
        self.record_button.clicked.connect(self.record_action); self.export_button.clicked.connect(self.request_export)
        self.refresh_button.clicked.connect(self.refresh); self.folder_button.clicked.connect(self.open_export_folder)
        self.help_button.clicked.connect(self.help)
        self.countdown = QtCore.QTimer(self); self.countdown.setInterval(countdown_ms); self.countdown.timeout.connect(self.advance_countdown)
        self.countdown.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self.poll_timer = QtCore.QTimer(self); self.poll_timer.setInterval(20); self.poll_timer.timeout.connect(self.poll); self.poll_timer.start()
        self.select_activity('standing')
        try: self.participant.setText(read(self.store.root / 'settings.json')['participant_id'])
        except (OSError, ValueError, KeyError): pass
        if self.participant.text(): self.change_participant()
        self.sync()
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(max(self.minimumWidth(), min(1280, available.width()-32)), max(self.minimumHeight(), min(760, available.height()-64)))
            self.move(available.x()+(available.width()-self.width())//2, available.y()+(available.height()-self.height())//2)

    def message(self, text, error=False):
        self.status.setText(text); self.status.setProperty('error', error); self.status.style().unpolish(self.status); self.status.style().polish(self.status)

    def technical_error(self, trace, user_message):
        try:
            folder = self.store.root / 'logs'; folder.mkdir(exist_ok=True)
            (folder / (uuid.uuid4().hex + '.log')).write_text(trace, encoding='utf-8')
        except OSError:
            pass  # Disk/permission failure must not hide the Vietnamese recovery message.
        self.message(user_message, True)

    def job(self, work, done, failure):
        job = Job(work); self.jobs.add(job)
        def completed(result, error):
            self.jobs.discard(job)
            if error: self.technical_error(error, failure); done(None)
            else: done(result)
        job.signals.done.connect(completed); QtCore.QThreadPool.globalInstance().start(job)

    def select_activity(self, key):
        if self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING','SAVING']: return
        self.exercise = key; self.activity_buttons[key].setChecked(True); self.scenario.clear(); self.angle.clear()
        self.scenario_label.setText('Tư thế' if key == 'standing' else 'Kịch bản')
        for value, label in OPTIONS[key][1]: self.scenario.addItem(label, value)
        for value in ([0,45,90] if key == 'standing' else [90,45,0]): self.angle.addItem(ANGLES[value], value)
        self.update_instruction()
        self.side_scroll.verticalScrollBar().setValue(0)

    def update_instruction(self):
        if self.scenario.currentData() is not None:
            self.instruction.setText(instruction(self.exercise, self.scenario.currentData()))
            self.instruction.setMinimumHeight(self.instruction.heightForWidth(310)+4)
        self.sync()

    def change_participant(self):
        if self.busy or self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING','SAVING']: return
        self.selection_generation += 1; self.inventory = []; self.consent.setChecked(False)
        try:
            self.session = self.store.session(self.participant.text().strip()); self.participant.setText(self.session['participant_id']); self.refresh()
        except Exception as exc:
            self.session = None
            if type(exc) is ValueError: self.message(str(exc), True)
            else: self.technical_error(traceback.format_exc(), 'Không đọc được thông tin phiên. Giữ nguyên dữ liệu và liên hệ trưởng nhóm để kiểm tra.')
            self.render_inventory(); self.sync()

    def render_inventory(self):
        self.progress_list.clear()
        self.progress_title.setText(f'Các lượt quay: {sum(r["valid"] for r in self.inventory)}/{len(self.inventory)} hợp lệ')
        for item in self.inventory:
            m = item['metadata']; ex = m.get('exercise_id'); sc = m.get('instructed_scenario_id'); angle = m.get('declared_camera_angle')
            label = OPTIONS.get(ex, ('Lượt quay chưa hoàn tất', []))[0]; scenario = dict(OPTIONS.get(ex, ('', []))[1]).get(sc, 'Chưa hoàn tất')
            row = QtWidgets.QListWidgetItem(f'{"✓" if item["valid"] else "○"} {label} · {scenario}\n{ANGLES.get(angle, "Chưa rõ góc")} · {m.get("recording_id", "")[-6:]} · {item["message"]}')
            row.setForeground(QtGui.QColor('#15803d' if item['valid'] else '#b45309')); self.progress_list.addItem(row)
        if not self.inventory: self.progress_list.addItem('○ Chưa quay — chỉ cần quay nội dung được giao.')

    def reveal_progress(self):
        # Wait for the updated list/layout before scrolling the verified row into view.
        QtCore.QTimer.singleShot(0, lambda: self.side_scroll.ensureWidgetVisible(self.progress_list, 0, 8))

    def refresh(self):
        if not self.session or self.busy: return
        self.busy = True; session = dict(self.session); token = self.selection_generation
        self.message('Đang kiểm tra các video đã lưu…'); self.sync()
        def done(result):
            self.busy = False
            if token == self.selection_generation:
                self.inventory = result or []; self.render_inventory()
                if result is not None: self.message('Đã kiểm tra dữ liệu. Có thể chọn nội dung tiếp theo; không tự bắt đầu quay.')
            self.sync()
        self.job(lambda: self.store.recover(session), done, 'Không đọc được tiến độ. Giữ nguyên dữ liệu và bấm Kiểm tra lại dữ liệu.')

    def choose_camera(self):
        if self.process is not None: return
        dialog = QtWidgets.QDialog(self); dialog.setWindowTitle('Chọn camera'); layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(QtWidgets.QLabel('Chọn nguồn rồi xác nhận bằng hình xem trước.\nSố camera chưa xác minh tên thiết bị.'))
        index = QtWidgets.QSpinBox(); index.setRange(0,15); index.setValue(self.source['index']); layout.addWidget(QtWidgets.QLabel('Số camera')); layout.addWidget(index)
        backend = QtWidgets.QComboBox(); backend.addItem('Camera Windows (MSMF)', 'MSMF'); backend.addItem('Chế độ tương thích khác (DSHOW)', 'DSHOW'); backend.setCurrentIndex(0 if self.source['backend']=='MSMF' else 1); layout.addWidget(backend)
        buttons = QtWidgets.QDialogButtonBox(); ok = buttons.addButton('Dùng camera này', QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole); buttons.addButton('Hủy', QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec(): self.source = dict(index=index.value(), backend=backend.currentData())

    def toggle_camera(self):
        if self.process is not None: self.close_camera(); return
        if self.state not in ['IDLE','ERROR'] or self.busy: return
        ctx = mp.get_context('spawn'); self.commands = ctx.Queue(32); self.events = ctx.Queue(64); self.previews = ctx.Queue(2); self.stop_take_ns = ctx.Value('q', 0)
        self.process = ctx.Process(target=capture_main, args=(str(self.store.root), self.release, self.source, self.commands, self.events, self.previews, self.stop_take_ns), kwargs=dict(factory=self.capture_factory, test_only=self.test_only), daemon=True)
        self.clean_exit = False; self.process.start(); self.opened_at = time.monotonic(); self.last_preview = self.opened_at; self.latest = None; self.state = 'OPENING'; self.message('Đang mở camera…'); self.sync()

    def send(self, kind, **values):
        if self.process is None or not self.process.is_alive(): raise RuntimeError('Camera chưa sẵn sàng. Hãy mở lại camera.')
        self.commands.put_nowait(dict(kind=kind, **values))

    def close_camera(self):
        if self.process is None: return
        if self.state in ['RECORDING','WAIT_FIRST','COUNTDOWN','PREPARING']: self.stop_take()
        try: self.send('CLOSE')
        except Exception: pass
        self.state = 'CLOSING'; self.camera_close_at = time.monotonic(); self.latest = None; self.preview.image = None; self.preview.update(); self.sync()

    def record_action(self):
        if self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING']: self.stop_take(); return
        if self.state != 'PREVIEW' or self.busy: return
        try:
            if not self.session or identifier(self.participant.text().strip()) != self.session['participant_id']: raise ValueError('Nhập và xác nhận mã người tham gia trước khi quay.')
            if not self.consent.isChecked(): raise ValueError('Vui lòng đồng ý ghi hình và chia sẻ với nhóm trước khi quay.')
            if self.latest is None or time.monotonic()-self.last_preview > 2: raise ValueError('Camera chưa có hình ảnh mới. Hãy mở lại camera.')
            check_space(self.store.root); task = declaration(self.exercise, self.scenario.currentData(), self.angle.currentData())
            self.state = 'PREPARING'; self.stop_take_ns.value = 0; self.timer_label.setText('00:00.0'); self.last_saved = None
            self.send('PREPARE', session=dict(self.session), task=task, consent=True); self.message('Đang chuẩn bị bộ ghi video…'); self.sync()
        except Exception as exc:
            if self.state == 'PREPARING': self.state = 'PREVIEW'
            if type(exc) is ValueError: self.message(str(exc), True)
            else: self.technical_error(traceback.format_exc(), 'Không thể bắt đầu quay. Hãy kiểm tra camera, dung lượng và quyền ghi thư mục dữ liệu rồi thử lại.')
            self.sync()

    def advance_countdown(self):
        if self.state != 'COUNTDOWN': self.countdown.stop(); return
        self.count -= 1
        if self.count > 0:
            self.countdown_values.append(str(self.count)); self.preview.countdown = str(self.count); self.preview.update()
        else:
            self.countdown.stop(); self.preview.countdown = 'BẮT ĐẦU!'; self.preview.update(); self.state = 'WAIT_FIRST'
            self.send('START', not_before_ns=time.perf_counter_ns()); self.message('Chờ khung hình đầu tiên để bắt đầu ghi…'); self.sync()

    def stop_take(self):
        if self.state not in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING']: return
        self.stop_take_ns.value = time.perf_counter_ns(); self.countdown.stop(); self.preview.countdown = ''; self.preview.update()
        self.state = 'SAVING'; self.message('Đang kiểm tra và lưu video...'); self.send('END'); self.sync()

    def poll(self):
        if self.process is not None:
            for _ in range(64):
                try: event = self.events.get_nowait()
                except (queue.Empty, OSError, ValueError): break
                kind = event['kind']
                if kind == 'OPENED': self.camera_info = event
                elif kind == 'PREPARED' and self.state == 'PREPARING':
                    self.state = 'COUNTDOWN'; self.count = 3; self.countdown_values = ['3']; self.preview.countdown = '3'; self.preview.update(); self.countdown.start(); self.message('Chuẩn bị — có thể bấm Hủy lượt quay.'); self.sync()
                elif kind == 'RECORDING' and self.state == 'WAIT_FIRST':
                    self.state = 'RECORDING'; self.preview.countdown = ''; self.preview.update(); self.message('ĐANG GHI HÌNH'); self.sync()
                elif kind == 'CLOSED':
                    self.countdown.stop(); self.preview.countdown = ''; self.preview.update(); self.busy = True
                    folder = event['folder']; session = dict(self.session); self.message('Đang kiểm tra và lưu video...'); self.sync()
                    def save_and_inventory(f=folder, selected=session):
                        saved_folder = None; problem = None
                        try: saved_folder = finalize_take(f)
                        except Exception: problem = traceback.format_exc()
                        return dict(folder=saved_folder, problem=problem, inventory=self.store.inventory(selected))
                    def saved(result):
                        self.busy = False; self.last_saved = result['folder'] if result else None
                        if self.state not in ['CLOSING','ERROR']: self.state = 'PREVIEW' if self.process is not None else 'IDLE'
                        if result:
                            self.inventory = result['inventory']; self.render_inventory(); self.reveal_progress()
                            if result['folder']: self.message('Đã lưu video thành công!')
                            elif result['problem']: self.technical_error(result['problem'], 'Cần quay lại — lượt quay đã hủy hoặc chưa vượt qua kiểm tra. Dữ liệu được giữ nguyên.')
                        if self.close_pending and not self.busy: self.close_camera()
                        self.sync()
                    self.job(save_and_inventory, saved, 'Cần quay lại — video chưa vượt qua kiểm tra. Dữ liệu được giữ nguyên trong mục incomplete.')
                elif kind == 'ERROR':
                    self.state = 'ERROR'; self.countdown.stop(); self.preview.countdown = ''; self.message(event['message'], True); self.sync()
                elif kind == 'EXITED': self.clean_exit = bool(event.get('camera_released'))
            for _ in range(4):
                try: frame = self.previews.get_nowait()
                except (queue.Empty, OSError, ValueError): break
                self.latest = frame; self.last_preview = time.monotonic()
                if self.state == 'OPENING': self.state = 'PREVIEW'; self.message('Đảm bảo cơ thể nằm trong khung hình. Chọn nội dung rồi bấm Bắt đầu quay.'); self.sync()
                if self.state not in ['CLOSING','ERROR']:
                    rgb = cv2.cvtColor(frame['frame'], cv2.COLOR_BGR2RGB); h,w = rgb.shape[:2]
                    self.preview.image = QtGui.QImage(rgb.data,w,h,rgb.strides[0],QtGui.QImage.Format.Format_RGB888).copy(); self.preview.update()
                if self.state == 'RECORDING':
                    elapsed = frame['elapsed_seconds']; self.timer_label.setText(f'{int(elapsed//60):02d}:{elapsed%60:04.1f}')
            alive = self.process.is_alive(); timeout = 15 if self.state == 'OPENING' else 5
            if alive and ((self.camera_close_at and time.monotonic()-self.camera_close_at > 5) or
                          (self.state not in ['CLOSING','SAVING'] and time.monotonic()-self.last_preview > timeout)):
                self.process.terminate(); self.state = 'ERROR'; self.message('Camera không phản hồi. Lượt chưa hoàn tất được giữ lại; hãy mở lại camera.', True)
            if not alive:
                self.process.join(0); self.process.close(); self.process = None; self.camera_close_at = None; self.latest = None; self.preview.image = None; self.preview.update()
                for q in [self.commands,self.events,self.previews]: q.close(); q.cancel_join_thread()
                if not self.clean_exit: self.state = 'ERROR'; self.message('Tiến trình camera dừng đột ngột. Dữ liệu chưa hoàn tất được giữ lại; hãy mở lại camera.', True)
                elif self.state not in ['ERROR','SAVING']: self.state = 'IDLE'; self.message('Camera đã đóng. Video đã lưu được giữ nguyên.')
                self.sync()
        if self.close_pending and self.process is None and not self.busy and not self.jobs:
            self.close_pending = False; self.close()

    def request_export(self):
        if self.busy or not self.session or not any(r['valid'] for r in self.inventory): return
        self.busy = True; session = dict(self.session); self.message('Đang kiểm tra lại các video trước khi xuất…'); self.sync()
        def checked(result):
            self.busy = False; self.inventory = result or []; self.render_inventory(); self.sync()
            if result and any(r['valid'] for r in result): self.show_export_dialog()
            elif result is not None: self.message('Không còn video hợp lệ để xuất. Video bị thiếu, thay đổi hoặc chưa hoàn tất; hãy kiểm tra hoặc quay lại.', True)
        self.job(lambda: self.store.inventory(session), checked, 'Không kiểm tra được dữ liệu. Hãy giữ nguyên video và thử lại.')

    def show_export_dialog(self):
        groups = {}
        for row in self.inventory:
            m = row['metadata']; key = (m.get('exercise_id'), m.get('instructed_scenario_id'), m.get('declared_camera_angle'))
            counts = groups.setdefault(key, [0, 0]); counts[0] += 1; counts[1] += int(row['valid'])
        lines = []
        for (ex, sc, angle), (total, valid) in groups.items():
            label, scenarios = OPTIONS.get(ex, ('Chưa rõ hoạt động', []))
            lines.append(f'{label} · {dict(scenarios).get(sc, "Chưa hoàn tất")} · {ANGLES.get(angle, "Chưa rõ góc")}: {total} lượt, {valid} hợp lệ')
        text = 'Vui lòng kiểm tra đã quay đủ nội dung được giao qua Zalo.\nChỉ video hợp lệ được đưa vào ZIP; ứng dụng không xác nhận đã đủ nhiệm vụ.\n\n' + '\n'.join(lines)
        if self.confirm_export is not None:
            approved = self.confirm_export(text)
        else:
            box = QtWidgets.QMessageBox(self); box.setWindowTitle('Kiểm tra trước khi xuất'); box.setText(text); yes = box.addButton('Chọn thư mục lưu ZIP', QtWidgets.QMessageBox.ButtonRole.AcceptRole); box.addButton('Hủy', QtWidgets.QMessageBox.ButtonRole.RejectRole); box.exec(); approved = box.clickedButton() == yes
        if not approved: return
        if self.dialog_factory is not None:
            destination = self.dialog_factory()
            if destination: self.begin_export(destination)
            return
        self.folder_dialog = QtWidgets.QFileDialog(self, 'Chọn thư mục lưu ZIP'); self.folder_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory); self.folder_dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly, True)
        self.folder_dialog.setLabelText(QtWidgets.QFileDialog.DialogLabel.Accept, 'Lưu ZIP tại đây'); self.folder_dialog.setLabelText(QtWidgets.QFileDialog.DialogLabel.Reject, 'Hủy')
        self.folder_dialog.accepted.connect(lambda: self.begin_export(self.folder_dialog.selectedFiles()[0])); self.folder_dialog.open()

    def begin_export(self, destination):
        if self.busy or self.state not in ['IDLE','PREVIEW','ERROR']: return
        self.busy = True; session = dict(self.session); self.message('Đang kiểm tra dữ liệu và tạo ZIP…'); self.sync()
        def done(result):
            self.busy = False
            if result:
                self.last_zip = result; p = Path(result['path']); self.message(f'Đã xuất dữ liệu thành công!\n{p.name} · {result["bytes"]/2**20:.2f} MiB · {result["recordings"]} video\nThư mục: {p.parent}'); self.folder_button.setVisible(True)
            self.sync()
        self.job(lambda: export_zip(self.store, session, destination, self.release), done, 'Xuất ZIP chưa thành công. Kiểm tra dung lượng/quyền ghi hoặc chọn thư mục khác. Video gốc được giữ nguyên; hãy kiểm tra lại dữ liệu rồi thử xuất lại.')

    def open_export_folder(self):
        if self.last_zip: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(self.last_zip['path']).parent)))

    def help(self):
        box = QtWidgets.QMessageBox(self); box.setWindowTitle('Hướng dẫn quay'); box.setText('1. Nhập mã được giao, không nhập tên thật.\n2. Chọn hoạt động, kịch bản và góc quay theo Zalo.\n3. Đồng ý ghi hình và chia sẻ với nhóm; mở camera và kiểm tra khung hình.\n4. Bắt đầu quay, chờ 3–2–1 rồi thực hiện trong khả năng thoải mái.\n5. Dừng và lưu; chỉ có dấu ✓ khi tệp đã kiểm tra.\n6. Có thể quay một hoạt động rồi xuất ZIP; tự gửi tệp qua Zalo.\n\n'+CONSENT+'\n\n'+PARENT_NOTICE); box.addButton('Đã hiểu', QtWidgets.QMessageBox.ButtonRole.AcceptRole); box.exec()

    def sync(self):
        if not hasattr(self, 'record_button'): return
        taking = self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING','SAVING']
        free = not taking and not self.busy and self.state != 'CLOSING'
        self.participant.setEnabled(free); self.consent.setEnabled(free)
        for b in self.activity_buttons.values(): b.setEnabled(free)
        self.scenario.setEnabled(free); self.angle.setEnabled(free); self.refresh_button.setEnabled(free and self.session is not None)
        self.camera_choice.setEnabled(free and self.process is None); self.camera_button.setEnabled(free and self.state in ['IDLE','ERROR','PREVIEW'])
        self.camera_button.setText('Đóng camera' if self.process is not None else 'Mở camera')
        self.record_button.setEnabled((self.state == 'PREVIEW' and not self.busy and self.session is not None and self.consent.isChecked()) or self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING'])
        self.record_button.setText('Dừng và lưu video' if self.state == 'RECORDING' else ('Hủy lượt quay' if self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST'] else 'Bắt đầu quay'))
        self.export_button.setEnabled(free and any(r['valid'] for r in self.inventory))

    def closeEvent(self, event):
        if self.process is not None or self.busy or self.jobs:
            event.ignore(); self.close_pending = True
            if self.state in ['PREPARING','COUNTDOWN','WAIT_FIRST','RECORDING']:
                self.stop_take(); self.close_camera()
            elif not self.busy and self.state != 'SAVING': self.close_camera()
            self.message('Đang dừng và lưu dữ liệu trước khi đóng…'); return
        self.poll_timer.stop(); self.countdown.stop(); self.lock.unlock(); event.accept()
