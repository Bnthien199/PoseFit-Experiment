"""Dedicated recorder entrypoint; no camera starts until the user requests preview."""
from pathlib import Path
import argparse, ctypes, json, multiprocessing as mp, sys, traceback


def main():
    parser=argparse.ArgumentParser(description='PoseFit — Thực nghiệm')
    parser.add_argument('--qt-provider',choices=['bundled','installed'],default='bundled')
    parser.add_argument('--preflight-only',action='store_true')
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent/'data')
    parser.add_argument('--smoke-exit-ms',type=int,default=0)
    args=parser.parse_args()
    try:
        from posefit_recorder.release import preflight,portable_identity
        report=preflight(args.qt_provider)
        if args.preflight_only:print(json.dumps(report,ensure_ascii=False,indent=2));return 0
        from PySide6 import QtCore,QtGui,QtWidgets
        from posefit_recorder.window import RecorderWindow
        app=QtWidgets.QApplication(sys.argv[:1]);app.setApplicationName('PoseFit — Thực nghiệm');app.setFont(QtGui.QFont('Segoe UI',10))
        window=RecorderWindow(args.data_dir,portable_identity());window.show()
        if args.smoke_exit_ms:QtCore.QTimer.singleShot(args.smoke_exit_ms,window.close)
        return app.exec()
    except Exception:
        trace=traceback.format_exc()
        if args.preflight_only:print(json.dumps(dict(PASS=False,message='Không khởi động được PoseFit. Kiểm tra tệp phát hành và môi trường thư viện.',technical_details=trace),ensure_ascii=False));return 2
        try:
            args.data_dir.mkdir(parents=True,exist_ok=True);(args.data_dir/'startup_error.log').write_text(trace,encoding='utf-8')
        except OSError:
            pass
        ctypes.windll.user32.MessageBoxW(None,'Không khởi động được PoseFit. Hãy dùng đúng môi trường cài đặt và bộ tệp đầy đủ. Chi tiết được giữ trong nhật ký lỗi của thư mục dữ liệu.','PoseFit — Cần kiểm tra',0x10)
        return 2


if __name__=='__main__':
    mp.freeze_support();raise SystemExit(main())
