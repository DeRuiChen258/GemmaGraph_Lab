"""Inspect GGUF metadata only; inference stays in upstream llama.cpp."""

import hashlib
import struct
from functools import lru_cache
from pathlib import Path


def inspect_gguf(path: Path) -> dict:
    stat = path.stat()
    return dict(_inspect(str(path.resolve()), stat.st_size, stat.st_mtime_ns))


@lru_cache(maxsize=8)
def _inspect(path: str, size: int, mtime_ns: int) -> dict:
    del mtime_ns
    with Path(path).open("rb") as stream:
        def read(count):
            result = stream.read(count)
            if len(result) != count:
                raise ValueError("GGUF 文件头被截断")
            return result

        def number(fmt):
            return struct.unpack("<" + fmt, read(struct.calcsize("<" + fmt)))[0]

        def string():
            length = number("Q")
            if length > 32 * 1024 * 1024:
                raise ValueError("GGUF metadata 字符串超出检查上限")
            return read(length).decode("utf-8")

        def value(kind, depth=0):
            formats = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i",
                       6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
            if kind == 8:
                return string()
            if kind == 9:
                subtype, count = number("I"), number("Q")
                if depth > 2 or count > 4_000_000:
                    raise ValueError("GGUF metadata 数组超出检查上限")
                for _ in range(count):
                    value(subtype, depth + 1)
                return None
            if kind not in formats:
                raise ValueError(f"未知 GGUF metadata 类型：{kind}")
            return number(formats[kind])

        if read(4) != b"GGUF":
            raise ValueError("模型不是 GGUF 文件")
        version, tensors, fields = number("I"), number("Q"), number("Q")
        if version != 3 or not 0 < fields < 100_000 or not tensors:
            raise ValueError("需要具有有效 metadata 的 GGUF v3 权重")
        wanted = {"general.architecture", "general.file_type", "gemma4.context_length",
                  "gemma4.block_count", "tokenizer.chat_template"}
        metadata = {}
        for _ in range(fields):
            name, kind = string(), number("I")
            item = value(kind)
            if name in wanted:
                metadata[name] = item
        template = metadata.pop("tokenizer.chat_template", None)
        return {"format": "GGUF", "version": version, "size_bytes": size,
                "tensor_count": tensors, "architecture": metadata.get("general.architecture"),
                "file_type": metadata.get("general.file_type"),
                "context_length": metadata.get("gemma4.context_length"),
                "block_count": metadata.get("gemma4.block_count"),
                "embedded_chat_template": bool(template),
                "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest() if template else None}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
