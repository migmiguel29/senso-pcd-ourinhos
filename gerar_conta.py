import getpass
import hashlib
import re
import secrets

user = input("Usuário: ").strip().lower()
if not re.fullmatch(r"[a-z0-9_.-]{3,100}", user):
    raise SystemExit("Use de 3 a 100 letras ASCII, números, ponto, hífen ou sublinhado.")
password = getpass.getpass("Senha: ")
if len(password) < 16 or len(password) > 256:
    raise SystemExit("Use de 16 a 256 caracteres.")
if password != getpass.getpass("Confirme a senha: "):
    raise SystemExit("Senhas diferentes.")
salt = secrets.token_bytes(16)
digest = hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024**2)
print(f'[usuarios."{user}"]\nsalt = "{salt.hex()}"\nhash = "{digest.hex()}"')
