"""Build a Blender extension ZIP with its manifest at the archive root."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
package = root / 'objmc_blender'
output = root / 'dist/objmc_blender-0.4.2.zip'
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(package.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            archive.write(path, path.relative_to(package).as_posix())
    archive.write(root / 'README.md', 'README.md')
print(output)
with zipfile.ZipFile(output) as archive:
    assert 'blender_manifest.toml' in archive.namelist()
    assert archive.testzip() is None
    print(f'{len(archive.namelist())} files; {output.stat().st_size} bytes; ZIP integrity OK')
