"""Selected-participant allowlist ZIP, hashes, CRC, temporary target and no overwrite."""
from pathlib import Path, PurePosixPath
from datetime import datetime
import hashlib
import os
import re
import stat
import uuid
import zipfile
from .storage import read, sha, json_bytes, validate_recording, publish, identifier, now, SCHEMA

RECORD_FILES = ['raw.avi', 'frames.csv', 'metadata.json', 'verified.json']


def safe_name(name):
    if not isinstance(name, str) or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('ZIP có đường dẫn không an toàn.')
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in ('..', '.') or x.endswith((' ', '.')) for x in p.parts) or str(p) != name:
        raise ValueError('ZIP có đường dẫn không an toàn.')
    return name


def verify_zip(path):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist(); names = [safe_name(i.filename) for i in infos]
        if len(names) != len(set(names)) or sum(i.file_size for i in infos) > 20 * 1024**3:
            raise ValueError('ZIP trùng tên tệp hoặc vượt giới hạn kiểm tra 20 GiB.')
        if any(i.is_dir() or i.flag_bits & 1 or stat.S_ISLNK(i.external_attr >> 16) for i in infos) or z.testzip() is not None:
            raise ValueError('ZIP không đọc được đầy đủ hoặc có lỗi CRC.')
        if 'manifest.json' not in names: raise ValueError('ZIP thiếu manifest.')
        import json
        manifest = json.loads(z.read('manifest.json'))
        if manifest['schema_version'] != SCHEMA or set(names) != set(manifest['files']) | {'manifest.json'}:
            raise ValueError('Danh sách tệp ZIP không khớp manifest.')
        pid = identifier(manifest['participant_id']); sid = manifest['session_id']
        rids = manifest['recording_ids']
        if not re.fullmatch(r'S[0-9a-f]{32}', sid) or not rids or len(rids) != len(set(rids)):
            raise ValueError('Thông tin phiên ZIP không hợp lệ.')
        expected = {'participant.json', 'release.json', 'validation_summary.json', 'consent_share.json'}
        for rid in rids:
            if not re.fullmatch(r'R[0-9a-f]{32}', rid): raise ValueError('Mã lượt quay không an toàn.')
            expected.update(f'recordings/{rid}/{n}' for n in RECORD_FILES)
        if set(manifest['files']) != expected: raise ValueError('ZIP có tệp ngoài danh sách cho phép.')
        for name, info in manifest['files'].items():
            safe_name(name); h = hashlib.sha256(); size = 0
            with z.open(name) as source:
                for block in iter(lambda: source.read(1024 * 1024), b''): h.update(block); size += len(block)
            if h.hexdigest() != info['sha256'] or size != info['bytes']:
                raise ValueError('SHA256 hoặc kích thước tệp trong ZIP không khớp.')
        participant = json.loads(z.read('participant.json'))
        consent = json.loads(z.read('consent_share.json'))
        if participant['participant_id'] != pid or participant['session_id'] != sid or consent['share_with_research_group'] is not True:
            raise ValueError('ZIP không thuộc người tham gia/phiên đã chọn hoặc thiếu đồng ý chia sẻ.')
        for rid in rids:
            base = 'recordings/' + rid + '/'
            m = json.loads(z.read(base + 'metadata.json')); v = json.loads(z.read(base + 'verified.json'))
            if (m['participant_id'] != pid or m['session_id'] != sid or m['recording_id'] != rid or
                    m['instruction_is_ground_truth'] is not False or m['human_ground_truth'] is not None or
                    m['recording_consent']['confirmed'] is not True or m['state'] != 'CLOSED' or
                    v['technical_valid'] is not True or v['recording_id'] != rid):
                raise ValueError('Metadata/consent của video không thuộc gói đã chọn.')
            for name in ['metadata.json', 'raw.avi', 'frames.csv']:
                if v['files'][name] != manifest['files'][base + name]['sha256']:
                    raise ValueError('Biên nhận video trong ZIP không khớp SHA256.')
        return dict(PASS=True, recordings=len(rids), participant_id=pid, session_id=sid,
                    files=len(names), physical_execution_verified=False)


def export_zip(store, session, destination, release, *, progress=None):
    pid = identifier(session['participant_id']); inventory = store.inventory(session)
    # A changed or incomplete take cannot silently disappear from the inventory.
    valid = [r for r in inventory if r['valid']]
    if not valid: raise ValueError('Cần ít nhất một video đã được kiểm tra để xuất ZIP.')
    destination = Path(destination).resolve()
    if not destination.is_dir(): raise ValueError('Thư mục xuất ZIP không tồn tại.')
    sources = {}
    for item in valid:
        folder = Path(item['folder']); m = item['metadata']; validate_recording(folder)
        if m['participant_id'] != pid or m['session_id'] != session['session_id']:
            raise ValueError('Từ chối dữ liệu không thuộc người tham gia và phiên đã chọn.')
        for name in RECORD_FILES:
            p = (folder / name).resolve()
            if not p.is_relative_to(store.root) or (folder / name).is_symlink():
                raise ValueError('Tệp dữ liệu liên kết ra ngoài thư mục được phép.')
            sources[f'recordings/{m["recording_id"]}/{name}'] = p
    records = [r['metadata'] for r in valid]
    docs = {
        'participant.json': dict(schema_version=SCHEMA, participant_id=pid, session_id=session['session_id']),
        'release.json': release,
        'consent_share.json': dict(share_with_research_group=True, manually_transfer_via_Zalo=True,
                                   source_consent_per_recording=True, formal_collection_approved=False),
        'validation_summary.json': dict(technical_valid_recordings=len(valid), excluded_incomplete_or_modified=len(inventory)-len(valid),
                                        recording_ids=[m['recording_id'] for m in records], checked_at=now(),
                                        assignment_completeness='NOT VERIFIED; tasks assigned externally', human_GT_created=False),
    }
    entries = {k: json_bytes(v) for k, v in docs.items()}
    filemap = {k: dict(bytes=len(v), sha256=hashlib.sha256(v).hexdigest()) for k, v in entries.items()}
    filemap.update({k: dict(bytes=p.stat().st_size, sha256=sha(p)) for k, p in sources.items()})
    manifest = dict(schema_version=SCHEMA, participant_id=pid, session_id=session['session_id'],
                    recording_ids=[m['recording_id'] for m in records], exported_at=now(), files=filemap,
                    instructions_are_GT=False, declared_angles_independently_verified=False)
    entries['manifest.json'] = json_bytes(manifest)
    temp = destination / ('.PoseFit_' + uuid.uuid4().hex + '.partial')
    # Keep incomplete output on error; source footage is never deleted.
    with temp.open('xb') as raw:
        with zipfile.ZipFile(raw, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
            for name, data in entries.items(): z.writestr(name, data)
            for i, (name, p) in enumerate(sources.items()):
                z.write(p, name)
                if sha(p) != filemap[name]['sha256']: raise ValueError('Dữ liệu thay đổi trong khi xuất ZIP. Hãy kiểm tra và thử lại.')
                if progress: progress(i + 1, len(sources))
        raw.flush(); os.fsync(raw.fileno())
    result = verify_zip(temp)
    base = f'PoseFit_{pid}_{datetime.now().astimezone():%Y%m%d_%H%M%S}'
    for suffix in range(10000):
        target = destination / (base + (f'_{suffix}' if suffix else '') + '.zip')
        try:
            publish(temp, target); break
        except FileExistsError:
            continue
    else:
        raise OSError('Không tạo được tên ZIP mới. Hãy chọn thư mục khác.')
    return dict(result, path=str(target), bytes=target.stat().st_size, sha256=sha(target))
