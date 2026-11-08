"""Exclusive takes, atomic journals and verified progress. No assignment database."""
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import math
import os
import re
import shutil
import time
import uuid
import cv2
import numpy as np
from .options import CONSENT, declaration

SCHEMA = 'POSEFIT_RECORDER_09H1_V1'
FRAME_FIELDS = ['saved_index', 'capture_sequence', 'read_started_ns', 'capture_monotonic_ns',
                'relative_capture_seconds', 'camera_pts_msec', 'width', 'height']


def now():
    return datetime.now().astimezone().isoformat(timespec='microseconds')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', value):
        raise ValueError('Mã người tham gia chỉ dùng chữ, số, dấu _ hoặc -, bắt đầu bằng chữ; tối đa 32 ký tự.')
    value = value.upper()
    if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', value):
        raise ValueError('Mã này được Windows dành riêng. Vui lòng chọn mã khác, ví dụ P001.')
    return value


def uid(prefix):
    return prefix + uuid.uuid4().hex


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def atomic_json(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + uuid.uuid4().hex[:12] + '.partial')
    with temp.open('xb') as f:
        f.write(json_bytes(value)); f.flush(); os.fsync(f.fileno())
    if replace:
        os.replace(temp, path)  # Only mutable settings/journal; never verified footage.
    else:
        publish(temp, path)


def publish(temp, final):
    """Atomic same-directory publication without replacing any existing file."""
    temp, final = Path(temp), Path(final)
    if os.name == 'nt':
        os.rename(temp, final)  # Windows rename fails if final exists.
    else:
        os.link(temp, final); temp.unlink()


def confined(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Đường dẫn dữ liệu không an toàn.')
    return path


def check_space(root, minimum=256 * 1024 * 1024):
    if shutil.disk_usage(root).free < minimum:
        raise OSError('Không đủ dung lượng trống. Cần ít nhất 256 MiB trước khi quay.')


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def session(self, participant):
        participant = identifier(participant)
        folder = confined(self.root, self.root / 'participants' / participant)
        longest = folder / ('S'+'0'*32) / 'incomplete' / ('R'+'0'*32) / ('.'+'0'*12+'.partial')
        if os.name == 'nt' and len(str(longest)) > 240:
            raise ValueError('Đường dẫn lưu quá dài cho Windows. Hãy đặt bộ chương trình trong thư mục ngắn hơn, ví dụ C:\\PoseFit, rồi mở lại.')
        folder.mkdir(parents=True, exist_ok=True)
        index = folder / 'session.json'
        if index.exists():
            s = read(index)
            if s.get('participant_id') != participant or not re.fullmatch(r'S[0-9a-f]{32}', s.get('session_id', '')):
                raise ValueError('Thông tin phiên bị hỏng. Giữ nguyên dữ liệu và liên hệ trưởng nhóm.')
        else:
            s = dict(schema_version=SCHEMA, participant_id=participant, session_id=uid('S'), created_at=now())
            atomic_json(index, s)
        (folder / s['session_id']).mkdir(exist_ok=True)
        atomic_json(self.root / 'settings.json', dict(participant_id=participant), replace=True)
        return s

    def folders(self, session):
        base = confined(self.root, self.root / 'participants' / identifier(session['participant_id']) / session['session_id'])
        result = []
        for name in ['recordings', 'incomplete']:
            p = base / name
            if p.exists():
                result.extend(confined(base, f) for f in sorted(p.iterdir()) if f.is_dir())
        return result

    def inventory(self, session):
        result = []
        for folder in self.folders(session):
            try:
                meta = read(folder / 'metadata.json')
                if meta['participant_id'] != session['participant_id'] or meta['session_id'] != session['session_id']:
                    raise ValueError('Bản ghi không thuộc người tham gia/phiên đã chọn.')
                validate_recording(folder)
                result.append(dict(folder=str(folder), metadata=meta, valid=True, message='Đã lưu thành công'))
            except Exception:
                try:
                    meta = read(folder / 'metadata.json') if (folder / 'metadata.json').exists() else read(folder / 'journal.json')
                except Exception:
                    meta = dict(recording_id=folder.name)
                result.append(dict(folder=str(folder), metadata=meta, valid=False,
                                   message='Cần quay lại — dữ liệu thiếu, thay đổi hoặc chưa hoàn tất.'))
        return result

    def recover(self, session):
        """Revalidate closed pending takes; never promote an interrupted/error writer."""
        for folder in self.folders(session):
            if folder.parent.name != 'incomplete': continue
            try:
                meta = read(folder / 'metadata.json')
                if meta.get('state') != 'CLOSED' or meta.get('participant_id') != session['participant_id'] or meta.get('session_id') != session['session_id']:
                    continue
                finalize_take(folder)
            except (OSError, ValueError, KeyError, TypeError):
                pass  # Keep original bytes and mark it incomplete in inventory below.
        return self.inventory(session)


class TakeWriter:
    """Camera-owner process only. Raw MJPG AVI and read-completion timestamps."""
    def __init__(self, root, release, *, writer_factory=None, minimum_free=256 * 1024 * 1024):
        self.store = Store(root); self.release = release
        self.factory = writer_factory or cv2.VideoWriter; self.minimum_free = minimum_free
        self.writer = None; self.file = None; self.n = 0; self.started = False; self.folder = None
        self.first_ns = self.last_ns = self.last_sequence = None

    def prepare(self, session, task, dimensions, fps, camera, consent, test_only=False):
        if self.writer is not None:
            raise ValueError('Đang có một lượt quay. Hãy dừng lượt hiện tại trước.')
        if consent is not True:
            raise ValueError('Cần đồng ý ghi hình và chia sẻ với nhóm trước khi quay.')
        identifier(session['participant_id']); declaration(task['exercise_id'], task['instructed_scenario_id'], task['declared_camera_angle'])
        check_space(self.store.root, self.minimum_free)
        w, h = dimensions
        if min(w, h) < 2 or not math.isfinite(fps) or not 1 <= fps <= 120:
            raise ValueError('Camera chưa cung cấp khung hình hoặc tốc độ hợp lệ.')
        rid = uid('R')
        base = confined(self.store.root, self.store.root / 'participants' / session['participant_id'] / session['session_id'])
        self.folder = base / 'incomplete' / rid; self.folder.mkdir(parents=True, exist_ok=False)
        self.meta = dict(task, schema_version=SCHEMA, participant_id=session['participant_id'], session_id=session['session_id'],
                         recording_id=rid, take_id=rid, prepared_at=now(), state='PREPARED',
                         recording_consent=dict(confirmed=True, confirmed_at=now(), text=CONSENT, simulated=bool(test_only)),
                         formal_collection_approved=False, collection_scope='ENGINEERING_OR_SEPARATELY_REVIEWED_PILOT',
                         test_only=bool(test_only), release=self.release, camera=camera,
                         observed_resolution=[w, h], encoded_fps=float(fps), codec='MJPG', audio_recorded=False,
                         overlays_recorded=False, inference_enabled=False,
                         source_frame_timestamps='frames.csv', timestamp_authority='read completion perf_counter_ns; not sensor exposure or posture GT')
        atomic_json(self.folder / 'journal.json', self.meta)
        self.n = 0; self.first_ns = self.last_ns = self.last_sequence = None
        try:
            self.writer = self.factory(str(self.folder / 'raw.avi'), cv2.VideoWriter_fourcc(*'MJPG'), fps, (w, h))
            if not self.writer.isOpened():
                raise OSError('Không khởi tạo được bộ ghi video. Hãy kiểm tra thư mục lưu và thử lại.')
            self.file = (self.folder / 'frames.csv').open('x', newline='', encoding='utf-8')
            self.csv = csv.DictWriter(self.file, fieldnames=FRAME_FIELDS); self.csv.writeheader(); self.file.flush()
        except Exception:
            self.abort('Không khởi tạo được bộ ghi video.'); raise
        self.n = 0; self.first_ns = self.last_ns = self.last_sequence = None
        self.start_after_ns = None; self.started = False; self.last_disk_check = time.monotonic()
        return rid

    def start(self, not_before_ns):
        if self.writer is None or self.started:
            raise ValueError('Bộ ghi chưa sẵn sàng hoặc đã bắt đầu.')
        self.start_after_ns = max(int(not_before_ns), time.perf_counter_ns())
        self.started = True
        self.meta['recording_start_not_before_ns'] = self.start_after_ns

    def append(self, frame, sequence, read_begin, capture_ns, pts=None):
        if not self.started or read_begin < self.start_after_ns:
            return False
        if not isinstance(capture_ns, int) or capture_ns < read_begin or (self.last_ns is not None and capture_ns <= self.last_ns):
            raise ValueError('Mốc thời gian camera không tăng. Lượt quay được giữ để kiểm tra.')
        if self.last_sequence is not None and sequence <= self.last_sequence:
            raise ValueError('Thứ tự khung hình không hợp lệ.')
        w, h = self.meta['observed_resolution']
        if frame is None or frame.dtype != np.uint8 or frame.shape != (h, w, 3):
            raise ValueError('Camera bị mất hình hoặc đổi kích thước. Vui lòng quay lại.')
        if time.monotonic() - self.last_disk_check > 1:
            check_space(self.store.root, self.minimum_free); self.last_disk_check = time.monotonic()
        if self.first_ns is None:
            self.first_ns = capture_ns; self.meta['start_timestamp'] = now()
        self.writer.write(frame)
        self.csv.writerow(dict(saved_index=self.n, capture_sequence=sequence, read_started_ns=read_begin,
                               capture_monotonic_ns=capture_ns, relative_capture_seconds=f'{(capture_ns-self.first_ns)/1e9:.9f}',
                               camera_pts_msec=pts if pts is not None and math.isfinite(pts) else '', width=w, height=h))
        self.file.flush()
        self.last_ns = capture_ns; self.last_sequence = sequence; self.n += 1
        return True

    def close(self, error=None):
        if self.writer is not None:
            try:
                self.writer.release()
            except Exception:
                error = error or 'Bộ ghi không đóng đúng cách.'
            self.writer = None
        if self.file is not None:
            try:
                self.file.flush(); os.fsync(self.file.fileno())
            except OSError:
                error = error or 'Không ghi đủ dữ liệu xuống ổ đĩa.'
            finally:
                self.file.close(); self.file = None
        if self.folder is None:
            return None
        duration = (self.last_ns-self.first_ns)/1e9 if self.n > 1 else 0.
        self.meta.update(state='INCOMPLETE' if error or self.n < 3 else 'CLOSED', error=error,
                         end_timestamp=now(), recorded_frame_count=self.n,
                         first_capture_ns=self.first_ns, last_capture_ns=self.last_ns, capture_duration_seconds=duration,
                         observed_frame_rate=(self.n-1)/duration if duration else None,
                         sensor_dropped_frame_count=None)
        folder = self.folder
        try:
            if (folder / 'raw.avi').exists(): self.meta['video_sha256'] = sha(folder / 'raw.avi')
            if (folder / 'frames.csv').exists(): self.meta['timestamps_sha256'] = sha(folder / 'frames.csv')
            atomic_json(folder / 'metadata.json', self.meta)
        finally:
            self.folder = None; self.started = False
        return folder

    def abort(self, message):
        return self.close(error=message)


def validate_recording(folder, *, require_receipt=True):
    folder = Path(folder)
    paths = {name: confined(folder, folder / name) for name in ['metadata.json', 'raw.avi', 'frames.csv']}
    m = read(paths['metadata.json'])
    if m['schema_version'] != SCHEMA or m['state'] != 'CLOSED' or m['recorded_frame_count'] < 3:
        raise ValueError('Video chưa hoàn tất hoặc chưa đủ khung hình sử dụng được.')
    identifier(m['participant_id'])
    if (not re.fullmatch(r'S[0-9a-f]{32}', m['session_id']) or not re.fullmatch(r'R[0-9a-f]{32}', m['recording_id']) or
            m['take_id'] != m['recording_id'] or m['release'].get('release_id') != 'posefit-experiment-09h1-v1' or
            not re.fullmatch(r'[0-9a-f]{64}', m['release'].get('release_manifest_sha256', ''))):
        raise ValueError('Danh tính phiên, lượt quay hoặc bản phát hành không hợp lệ.')
    declaration(m['exercise_id'], m['instructed_scenario_id'], m['declared_camera_angle'])
    if m.get('instruction_is_ground_truth') is not False or m.get('human_ground_truth') is not None or m.get('machine_predictions') is not None:
        raise ValueError('Lời hướng dẫn không được coi là Ground Truth hoặc dự đoán mô hình.')
    if m['standing_posture'] != (m['instructed_scenario_id'] if m['exercise_id'] == 'standing' else None):
        raise ValueError('Tùy chọn tư thế không khớp.')
    if m['recording_consent']['confirmed'] is not True or m.get('formal_collection_approved') is not False:
        raise ValueError('Trạng thái đồng ý hoặc cổng thu thập không hợp lệ.')
    if sha(paths['raw.avi']) != m['video_sha256'] or sha(paths['frames.csv']) != m['timestamps_sha256']:
        raise ValueError('Video hoặc timestamps đã thay đổi. Không đánh dấu hoàn thành.')
    with paths['frames.csv'].open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != m['recorded_frame_count']:
        raise ValueError('Số khung hình và timestamps không khớp.')
    previous_ns = previous_seq = None
    first = int(rows[0]['capture_monotonic_ns'])
    for i, row in enumerate(rows):
        ns, seq, begin = int(row['capture_monotonic_ns']), int(row['capture_sequence']), int(row['read_started_ns'])
        rel = float(row['relative_capture_seconds'])
        if (int(row['saved_index']) != i or ns < begin or begin < m['recording_start_not_before_ns'] or
                (m.get('stop_requested_ns') is not None and ns >= m['stop_requested_ns']) or
                (previous_ns is not None and ns <= previous_ns) or (previous_seq is not None and seq <= previous_seq) or
                not math.isfinite(rel) or abs(rel - (ns-first)/1e9) > 1e-8 or
                [int(row['width']), int(row['height'])] != m['observed_resolution']):
            raise ValueError('Timestamps, thứ tự hoặc kích thước khung hình không hợp lệ.')
        previous_ns, previous_seq = ns, seq
    duration = (previous_ns-first)/1e9
    if (first != m['first_capture_ns'] or previous_ns != m['last_capture_ns'] or duration <= 0 or
            abs(duration-m['capture_duration_seconds']) > 1e-8 or
            abs((len(rows)-1)/duration-m['observed_frame_rate']) > 1e-7):
        raise ValueError('Thời gian thực của bản ghi không khớp timestamps.')
    cap = cv2.VideoCapture(str(paths['raw.avi']))
    n = 0
    try:
        if not cap.isOpened(): raise ValueError('Không giải mã được video. Giữ nguyên dữ liệu và quay lại.')
        while True:
            ok, frame = cap.read()
            if not ok: break
            if [frame.shape[1], frame.shape[0]] != m['observed_resolution']:
                raise ValueError('Video giải mã có kích thước không khớp.')
            n += 1
    finally:
        cap.release()
    if n != len(rows): raise ValueError('Video không giải mã đủ số khung hình đã ghi.')
    hashes = {k: sha(v) for k, v in paths.items()}
    if require_receipt:
        receipt = read(folder / 'verified.json')
        if receipt.get('files') != hashes or receipt.get('recording_id') != m['recording_id'] or receipt.get('technical_valid') is not True:
            raise ValueError('Biên nhận kiểm tra thiếu hoặc không còn khớp dữ liệu.')
    return dict(technical_valid=True, recording_id=m['recording_id'], decoded_frames=n, files=hashes,
                timestamp_rows=len(rows), human_execution_verified=False)


def finalize_take(folder):
    folder = Path(folder)
    result = validate_recording(folder, require_receipt=False)
    if (folder / 'verified.json').exists():
        validate_recording(folder)  # A prior receipt is never replaced or ignored.
    else:
        atomic_json(folder / 'verified.json', dict(result, verified_at=now()))
    target = folder.parent.parent / 'recordings' / folder.name
    target.parent.mkdir(exist_ok=True)
    if target.exists(): raise FileExistsError('Lượt quay đã tồn tại; không ghi đè dữ liệu cũ.')
    os.rename(folder, target)
    validate_recording(target)
    return str(target)
