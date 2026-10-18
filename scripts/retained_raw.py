"""Verify and carry registered raw snapshots, including offline export companions."""
import hashlib
from pathlib import Path
import re
import shutil

from common import DataError


def checked_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise DataError('Raw snapshot path must be a nonempty string')
    path = Path(relative)
    if path.is_absolute() or path.drive or '..' in path.parts or not path.parts or path.parts[0] != 'raw':
        raise DataError('Raw snapshot must be a relative path under raw/.')
    target = (Path(root) / path).resolve()
    if not target.is_relative_to((Path(root) / 'raw').resolve()):
        raise DataError('Raw snapshot escapes the raw directory')
    return target


def artifacts(bundle, include_audit=True):
    result = {}
    sources = list(bundle.get('sources', {}).values())
    if include_audit:
        sources += [dict(source_type='impact_data', raw_file=r['raw_file'], sha256_raw=r['sha256'])
                    for r in bundle.get('impact_collection', {}).get('requests', []) if r.get('raw_file')]
    for source in sources:
        if source.get('source_type') not in {'impact_data', 'kaggle_data'}:
            continue
        extra = source.get('raw_artifacts', [])
        if not isinstance(extra, list) or not all(isinstance(a, dict) for a in extra):
            raise DataError('Invalid registered raw companion list')
        records = ([source] if source.get('raw_file') else []) + extra
        for record in records:
            relative, checksum = record.get('raw_file'), record.get('sha256_raw')
            if not isinstance(relative, str) or not isinstance(checksum, str) or not re.fullmatch('[a-f0-9]{64}', checksum):
                raise DataError('Raw artifact needs path and SHA-256')
            if relative in result and result[relative] != checksum:
                raise DataError('Conflicting hashes for retained raw file')
            result[relative] = checksum
    return result


def verify_retained(bundle, root, include_audit=True):
    result = artifacts(bundle, include_audit)
    for relative, checksum in result.items():
        path = checked_path(root, relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise DataError('Imported raw snapshot differs from registered hash or is missing: ' + relative)
    if bundle.get('epm_import') is not None:
        from import_epm import validate_files
        validate_files(bundle, Path(root))
    if bundle.get('historical_epm_import') is not None:
        from historical_epm import validate_files as validate_historical_files
        validate_historical_files(bundle, Path(root))
    if bundle.get('advanced_percentile_populations') is not None:
        from advanced_percentiles import verify_files
        verify_files(bundle, Path(root))
    return result


def copy_retained(bundle, origin, destination):
    for relative in verify_retained(bundle, origin):
        target = checked_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checked_path(origin, relative), target)
