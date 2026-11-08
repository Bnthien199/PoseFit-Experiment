"""Explicit providers and release preflight; no camera or model load."""
from pathlib import Path
import hashlib, importlib.metadata, json, sys
BASE=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def preflight(provider='bundled'):
    from .trusted import MANIFEST_SHA256
    if provider not in ['bundled','installed']:raise ValueError('Nguồn thư viện không được hỗ trợ.')
    if sys.version_info[:2]!=(3,11):raise ValueError('Ứng dụng cần Python 3.11. Hãy dùng môi trường đã cài cho PoseFit.')
    path=BASE/'release_manifest.json'
    if sha(path)!=MANIFEST_SHA256:raise ValueError('Manifest phát hành đã thay đổi. Hãy lấy lại bản đầy đủ từ trưởng nhóm.')
    m=json.loads(path.read_text('utf-8'))
    for name, item in m['sources'].items():
        p=(BASE/name).resolve()
        if not p.is_relative_to(BASE) or p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
            raise ValueError('Tệp chương trình thiếu hoặc đã thay đổi. Hãy lấy lại bản đầy đủ.')
    if provider=='bundled':
        sys.path.insert(0,str(BASE/'deps'))
        vendor=json.loads((BASE/'dependency_manifest.json').read_text('utf-8'))
        # Inventory schema is inherited and explicitly inspected by the build.
        for name,item in vendor['files'].items():
            p=(BASE/name).resolve()
            if not p.is_relative_to(BASE/'deps') or not p.is_file() or p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
                raise ValueError('Bộ thư viện Qt thiếu hoặc sai hash. Hãy khôi phục bộ phát hành đầy đủ.')
    versions={}
    for dist, expected in m['requirements'].items():
        try:versions[dist]=importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:raise ValueError('Thiếu thư viện cần thiết. Hãy chạy bước cài đặt PoseFit.') from None
        if versions[dist]!=expected:raise ValueError('Phiên bản thư viện không đúng. Hãy dùng môi trường cài đặt riêng của PoseFit.')
    import numpy, cv2, PySide6, shiboken6
    site=(Path(sys.prefix)/'Lib/site-packages').resolve()
    origins={}
    for name,module in [('numpy',numpy),('cv2',cv2),('PySide6',PySide6),('shiboken6',shiboken6)]:
        origin=Path(module.__file__).resolve(); approved=(BASE/'deps').resolve() if provider=='bundled' and name in ['PySide6','shiboken6'] else site
        if not origin.is_relative_to(approved):raise ValueError('Ứng dụng đang nạp thư viện từ môi trường khác. Hãy dùng đúng lối mở PoseFit.')
        origins[name]=str(origin)
    parent=json.loads((BASE/'parent_gate.json').read_text('utf-8'))
    if parent['engineering_readiness']!='B' or parent['formal_human_data_collection_ready'] is not False:
        raise ValueError('Cổng review của bản nền không hợp lệ.')
    return dict(PASS=True,release_id=m['release_id'],manifest_sha256=MANIFEST_SHA256,provider=provider,
                versions=versions,origins=origins,formal_human_data_collection_ready=False,parent_review_pending=True,
                inference_enabled=False,camera_opened=False)


def portable_identity():
    from .trusted import MANIFEST_SHA256
    return dict(release_id='posefit-experiment-09h1-v1',release_manifest_sha256=MANIFEST_SHA256,
                parent_release_id='posefit-09g7-release-v1',parent_engineering_decision='B',
                parent_preservation_exception_open=True,formal_collection_approved=False)
