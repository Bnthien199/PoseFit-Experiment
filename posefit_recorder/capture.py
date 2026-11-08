"""One owned camera process. No inference; preview copies never enter the raw writer."""
import ctypes
import os
import queue
import time
import math
from collections import deque
import cv2
from .storage import TakeWriter


class CameraLease:
    def __init__(self, index): self.index = index; self.handle = None
    def acquire(self):
        if os.name == 'nt':
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel = kernel
            ctypes.set_last_error(0)
            self.handle = kernel.CreateMutexW(None, False, f'Local\\PoseFit09H1Camera_{self.index}')
            if not self.handle: raise OSError('Không tạo được khóa camera.')
            if ctypes.get_last_error() == 183:
                self.release(); raise OSError('Camera đang được một cửa sổ PoseFit khác sử dụng. Hãy đóng cửa sổ đó trước.')
    def release(self):
        if self.handle is not None: self.kernel.CloseHandle(self.handle); self.handle = None


def capture_main(root, release, source, commands, events, previews, stop_take_ns, *, factory=None, test_only=False):
    cap = None; lease = CameraLease(source['index']); writer = TakeWriter(root, release)
    sequence = 0; times = deque(maxlen=60); last_preview = 0.; closing = False
    def send(kind, **data): events.put(dict(kind=kind, **data), timeout=1)
    def end(error=None):
        if writer.folder is not None:
            writer.meta['stop_requested_ns'] = stop_take_ns.value or None
            folder = writer.close(error)
            send('CLOSED', folder=str(folder), error=error)
    try:
        lease.acquire()
        cap = (factory or cv2.VideoCapture)(source['index'], getattr(cv2, 'CAP_' + source['backend']))
        if not cap.isOpened():
            raise OSError('Không mở được camera. Kiểm tra quyền Windows, chọn lại camera hoặc đóng ứng dụng khác đang dùng camera.')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720); cap.set(cv2.CAP_PROP_FPS, 30)
        try: actual_backend = cap.getBackendName()
        except (AttributeError, cv2.error): actual_backend = None
        reported_fps = float(cap.get(cv2.CAP_PROP_FPS)); reported_fps = reported_fps if math.isfinite(reported_fps) else None
        send('OPENED', index=source['index'], backend=source['backend'], actual_backend=actual_backend, reported_fps=reported_fps)
        while not closing:
            while True:
                try: cmd = commands.get_nowait()
                except queue.Empty: break
                if cmd['kind'] == 'PREPARE':
                    if not times: raise ValueError('Chưa có preview. Hãy chờ hình ảnh camera xuất hiện.')
                    observed = (len(times)-1)/((times[-1]-times[0])/1e9) if len(times)>1 else 30.
                    fps = min(120., max(1., observed))
                    writer.prepare(cmd['session'], cmd['task'], dimensions, fps,
                                   dict(index=source['index'], backend=source['backend'], actual_backend=actual_backend, reported_fps=reported_fps, device_name=None,
                                        identity_verified=False, requested_fps=30, requested_resolution=[1280,720]),
                                   cmd['consent'], test_only=test_only)
                    send('PREPARED', recording_id=writer.meta['recording_id'])
                elif cmd['kind'] == 'START': writer.start(cmd['not_before_ns'])
                elif cmd['kind'] == 'END': end()
                elif cmd['kind'] == 'CLOSE': closing = True; end('Đã đóng camera khi lượt quay chưa hoàn tất.'); break
            if closing: break
            begin = time.perf_counter_ns(); ok, frame = cap.read(); ns = time.perf_counter_ns()
            if not ok or frame is None:
                raise OSError('Camera bị ngắt hoặc không còn hình ảnh. Dữ liệu đang quay được giữ để kiểm tra; hãy kết nối và mở lại camera.')
            dimensions = (frame.shape[1], frame.shape[0]); times.append(ns)
            if writer.started and (not stop_take_ns.value or ns < stop_take_ns.value):
                first = writer.n == 0
                written = writer.append(frame, sequence, begin, ns, float(cap.get(cv2.CAP_PROP_POS_MSEC)))
                if first and written: send('RECORDING', first_capture_ns=ns, recording_id=writer.meta['recording_id'])
            if time.monotonic()-last_preview >= .09:
                last_preview = time.monotonic()
                message = dict(frame=frame.copy(), sequence=sequence, capture_ns=ns,
                               dimensions=list(dimensions), recording=writer.started,
                               recorded_frames=writer.n, elapsed_seconds=(ns-writer.first_ns)/1e9 if writer.started and writer.first_ns else 0.)
                try: previews.put_nowait(message)
                except queue.Full:
                    try: previews.get_nowait()
                    except queue.Empty: pass
                    try: previews.put_nowait(message)
                    except queue.Full: pass
            sequence += 1
    except Exception as exc:
        known = ('Không mở được camera.', 'Camera bị ngắt hoặc không còn hình ảnh.', 'Camera đang được một cửa sổ PoseFit khác', 'Không đủ dung lượng trống.')
        message = str(exc) if type(exc) in (ValueError, OSError) and str(exc).startswith(known) else 'Lỗi camera hoặc ghi video. Kiểm tra dung lượng, quyền truy cập và kết nối rồi thử lại. Dữ liệu chưa hoàn tất được giữ nguyên.'
        try: end(message)
        except Exception: pass
        try: send('ERROR', message=message)
        except Exception: pass
    finally:
        try: end('Lượt quay chưa hoàn tất; dữ liệu được giữ lại.')
        except Exception: pass
        if cap is not None: cap.release()
        lease.release()
        try: send('EXITED', camera_released=True)
        except Exception: pass
        # Preview is disposable; never wait forever for GUI to consume queued images.
        previews.cancel_join_thread()
