"""Run in the project's terminal; token input is hidden and never logged."""
import getpass,json,os,re
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
target=root/'.runtime/ngrok-auth.json'
assert target.resolve().is_relative_to(root/'.runtime')
token=getpass.getpass('ngrok authtoken (hidden): ').strip()
if not re.fullmatch(r'[A-Za-z0-9_-]{21,300}',token):raise SystemExit('Invalid token format; nothing saved.')
descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(descriptor,'w') as output:
    json.dump({'authtoken':token},output);output.flush();os.fsync(output.fileno())
print('Token stored in the project private runtime; value hidden. Public tunnel remains disabled.')
