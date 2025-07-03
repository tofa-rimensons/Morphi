from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
import base64
from PIL import Image, UnidentifiedImageError
import numpy as np
import io


class CryptographyRepo:
    def __init__(self, password):
        self.block_size = 16
        self.key = self.derive_key(password)

    def pad(self, data: bytes) -> bytes:
        return data + b'\0' * (self.block_size - len(data) % self.block_size)

    def unpad(self, data: bytes) -> bytes:
        return data.rstrip(b'\0')

    def derive_key(self, password: str, key_len: int = 16) -> bytes:
        return PBKDF2(password, salt=bytes([0]), dkLen=key_len, count=1000)

    def encrypt_int(self, n: int) -> str:
        b = n.to_bytes(self.block_size, 'big')
        cipher = AES.new(self.key, AES.MODE_ECB)
        encrypted = cipher.encrypt(self.pad(b))
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_int(self, enc_str: str) -> int:
        encrypted = base64.urlsafe_b64decode(enc_str)
        cipher = AES.new(self.key, AES.MODE_ECB)
        decrypted = cipher.decrypt(encrypted)
        return int.from_bytes(self.unpad(decrypted), 'big')



    def encrypt_file(self, file_io: io.BytesIO) -> io.BytesIO:
        raw_bytes = file_io.getvalue()
        padded = self.pad(raw_bytes)
        cipher = AES.new(self.key, AES.MODE_ECB)
        encrypted = cipher.encrypt(padded)

        out_io = io.BytesIO(encrypted)
        out_io.seek(0)
        return out_io

    def decrypt_file(self, file_io: io.BytesIO) -> io.BytesIO:
        encrypted_bytes = file_io.getvalue()
        cipher = AES.new(self.key, AES.MODE_ECB)
        decrypted_padded = cipher.decrypt(encrypted_bytes)
        decrypted = self.unpad(decrypted_padded)

        out_io = io.BytesIO(decrypted)
        out_io.seek(0)
        return out_io
    
    
    def resize_and_optimize_if_image(self, input_bytes: bytes, max_size=1080, quality=90) -> io.BytesIO:
        file = Image.open(io.BytesIO(input_bytes))

        try:
            file.verify() 
        except (UnidentifiedImageError, OSError):
            return file
        
        img = file.convert('RGB')  # convert to RGB for JPEG

        # Calculate new size preserving aspect ratio
        width, height = img.size
        if max(width, height) > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        out_io = io.BytesIO()
        img.save(
            out_io,
            format='JPEG',
            quality=quality,          # controls compression, 85 is good default
            optimize=True,            # optimize Huffman coding
            progressive=True          # makes JPEG progressive
        )
        out_io.seek(0)
        return out_io
