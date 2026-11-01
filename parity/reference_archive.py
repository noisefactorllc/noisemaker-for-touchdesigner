"""Authenticate regular reference files against existing immutable Git objects."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess


def verify_archive(root, git_dir, requested, *, materialize=False):
    root, git_dir = Path(root), Path(git_dir)
    if not re.fullmatch(r'[0-9a-f]{40}', requested):
        raise ValueError('Archive authority requires an exact commit SHA.')
    if root.is_symlink() or git_dir.is_symlink() or not root.is_dir() or not git_dir.is_dir():
        raise ValueError('Archive and object store must be regular directories.')
    if (git_dir / 'commondir').exists() or (git_dir / 'objects').is_symlink():
        raise ValueError('Object store indirection is not permitted.')
    visited = 0
    for directory, dirs, files in os.walk(git_dir / 'objects', followlinks=False):
        for name in dirs + files:
            visited += 1
            path = Path(directory) / name
            if visited > 1000000 or path.is_symlink():
                raise ValueError('Object store contains links or exceeds the bounded inventory.')
            metadata = path.lstat()
            if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)):
                raise ValueError('Object store contains a nonregular entry.')
    config = git_dir / 'config'
    if config.is_symlink() or not config.is_file():
        raise ValueError('Object store configuration must be a regular file.')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull, GIT_NO_REPLACE_OBJECTS='1',
               GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')

    def command(args, **kwargs):
        try:
            return subprocess.check_output(['git', *args], env=env, stderr=subprocess.PIPE, **kwargs)
        except (OSError, subprocess.CalledProcessError) as error:
            raise ValueError('Cannot authenticate the requested Git objects.') from error

    # Read only this file, without expanding includes or consulting repository configuration.
    entries = command(['config', '--no-includes', '--file', str(config), '--null', '--list'])
    safe_core = {'repositoryformatversion', 'filemode', 'bare', 'logallrefupdates',
                 'ignorecase', 'precomposeunicode', 'symlinks'}
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        key = entry.split(b'\n', 1)[0].decode().lower()
        if key.startswith('core.') and key[5:] in safe_core:
            continue
        if re.fullmatch(r'remote\.[^.]+\.(url|fetch)|branch\.[^.]+\.(remote|merge)', key):
            continue
        raise ValueError('Object store configuration contains an unsupported setting.')
    if (git_dir / 'objects/info/alternates').exists() or (git_dir / 'objects/info/http-alternates').exists():
        raise ValueError('Object store alternates are not permitted.')
    args = ['--no-replace-objects', '--git-dir=' + str(git_dir),
            '-c', 'protocol.allow=never', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=' + os.devnull]
    commit = command([*args, 'rev-parse', '--verify', requested + '^{commit}']).decode().strip()
    if commit != requested:
        raise ValueError('Observed archive authority differs from the requested commit.')
    tree = command([*args, 'rev-parse', '--verify', requested + '^{tree}']).decode().strip()
    entries = command([*args, 'ls-tree', '-rtz', '--full-tree', requested])
    object_types = {commit: 'commit', tree: 'tree'}
    for entry in entries.split(b'\0'):
        if entry:
            mode, kind, oid = entry.split(b'\t', 1)[0].decode().split()
            if kind == 'tree':
                object_types[oid] = 'tree'
    objects = command([*args, 'cat-file', '--batch'],
                      input=('\n'.join(object_types) + '\n').encode())
    offset = 0
    for oid, expected_type in object_types.items():
        end = objects.index(b'\n', offset)
        actual_oid, kind, size = objects[offset:end].decode().split()
        payload = objects[end + 1:end + 1 + int(size)]
        digest = hashlib.sha1(kind.encode() + b' ' + size.encode() + b'\0' + payload).hexdigest()
        if actual_oid != oid or kind != expected_type or digest != oid:
            raise ValueError('Reference commit or tree object failed content authentication.')
        if kind == 'commit':
            headers = payload.split(b'\n\n', 1)[0].splitlines()
            if [line[5:] for line in headers if line.startswith(b'tree ')] != [tree.encode()]:
                raise ValueError('Reference tree differs from the authenticated commit tree.')
        offset = end + 2 + int(size)
    expected, alias = {}, None
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, kind, blob = meta.decode().split()
        path = raw_path.decode()
        if kind == 'tree':
            continue
        if path.startswith('/') or '..' in Path(path).parts or kind != 'blob':
            raise ValueError('Unsupported reference tree entry.')
        if mode == '120000':
            target = command([*args, 'cat-file', 'blob', blob])
            if hashlib.sha1(b'blob ' + str(len(target)).encode() + b'\0' + target).hexdigest() != blob:
                raise ValueError('Reference alias blob failed content authentication.')
            if path != 'shaders/share' or target != b'../share' or alias is not None:
                raise ValueError('Unsupported reference alias.')
            alias = {'path': path, 'target': 'share', 'git_blob': blob}
        elif mode in ('100644', '100755'):
            expected[path] = (mode, blob)
        else:
            raise ValueError('Unsupported reference file mode.')
    if alias:
        target_files = {p[len('share/'):]: value for p, value in expected.items() if p.startswith('share/')}
        if not target_files:
            raise ValueError('Reference alias target is empty.')
        for relative, value in target_files.items():
            expected['shaders/share/' + relative] = value
    if materialize:
        if any(root.iterdir()):
            raise ValueError('Archive materialization requires an empty directory.')
        blobs = list(dict.fromkeys(blob for mode, blob in expected.values()))
        packed = command([*args, 'cat-file', '--batch'], input=('\n'.join(blobs) + '\n').encode())
        payloads, position = {}, 0
        for blob in blobs:
            end = packed.index(b'\n', position)
            actual_oid, kind, size = packed[position:end].decode().split()
            payload = packed[end + 1:end + 1 + int(size)]
            digest = hashlib.sha1(b'blob ' + size.encode() + b'\0' + payload).hexdigest()
            if actual_oid != blob or kind != 'blob' or digest != blob:
                raise ValueError('Reference blob failed content authentication.')
            payloads[blob] = payload
            position = end + 2 + int(size)
        for relative, (mode, blob) in expected.items():
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payloads[blob])
            destination.chmod(0o755 if mode == '100755' else 0o644)
    actual = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError('Reference archives cannot contain symbolic links.')
        for name in files:
            path = Path(directory) / name
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError('Reference archives must contain regular files.')
            relative = path.relative_to(root).as_posix()
            mode = stat.S_IMODE(metadata.st_mode)
            data = path.read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            actual[relative] = ('100755' if mode == 0o755 else '100644' if mode == 0o644 else str(mode), blob)
    if actual != expected:
        raise ValueError('Reference archive inventory, file modes, or blob bytes differ from the authority.')
    inventory = json.dumps(sorted(actual.items()), separators=(',', ':')).encode()
    return {'kind': 'verified-archive', 'commit': commit, 'tree': tree,
            'inventory_sha256': hashlib.sha256(inventory).hexdigest(), 'projection': alias}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--materialize', action='store_true')
    parser.add_argument('root')
    parser.add_argument('object_store')
    parser.add_argument('commit')
    options = parser.parse_args()
    print(json.dumps(verify_archive(options.root, options.object_store, options.commit,
                                    materialize=options.materialize), sort_keys=True))
