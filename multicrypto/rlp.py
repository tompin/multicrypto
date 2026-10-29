"""Recursive Length Prefix (RLP) serialization used by Ethereum.

Items are byte strings or lists of items, integers are encoded as big endian byte strings
without leading zeros. Specification:
https://ethereum.org/developers/docs/data-structures-and-encoding/rlp/
"""

from typing import List, Tuple, Union

Item = Union[bytes, int, List['Item']]

SHORT_STRING = 0x80
LONG_STRING = 0xB7
SHORT_LIST = 0xC0
LONG_LIST = 0xF7
MAX_SHORT_LENGTH = 55


def int_to_bytes(value: int) -> bytes:
    if value < 0:
        raise ValueError(f'RLP cannot encode negative integer {value}')
    return value.to_bytes((value.bit_length() + 7) // 8, 'big')


def _encode_length(length: int, offset: int) -> bytes:
    if length <= MAX_SHORT_LENGTH:
        return bytes([offset + length])
    encoded_length = int_to_bytes(length)
    return bytes([offset + MAX_SHORT_LENGTH + len(encoded_length)]) + encoded_length


def encode(item: Item) -> bytes:
    if isinstance(item, int):
        item = int_to_bytes(item)
    if isinstance(item, (bytes, bytearray)):
        if len(item) == 1 and item[0] < SHORT_STRING:
            return bytes(item)
        return _encode_length(len(item), SHORT_STRING) + item
    payload = b''.join(encode(element) for element in item)
    return _encode_length(len(payload), SHORT_LIST) + payload


def _decode_length(data: bytes, position: int, short_offset: int, long_offset: int):
    """Position of the payload and its length for the prefix at the position."""
    prefix = data[position]
    if prefix <= long_offset:
        return position + 1, prefix - short_offset
    length_size = prefix - long_offset
    encoded_length = data[position + 1 : position + 1 + length_size]
    if len(encoded_length) != length_size:
        raise ValueError('RLP data is too short')
    length = int.from_bytes(encoded_length, 'big')
    if encoded_length[0] == 0 or length <= MAX_SHORT_LENGTH:
        raise ValueError('RLP length is not in the shortest long form')
    return position + 1 + length_size, length


def _decode_item(data: bytes, position: int) -> Tuple[Item, int]:
    """Item at the position and the position after it."""
    prefix = data[position]
    if prefix < SHORT_STRING:
        return data[position : position + 1], position + 1
    is_list = prefix >= SHORT_LIST
    if is_list:
        start, length = _decode_length(data, position, SHORT_LIST, LONG_LIST)
    else:
        start, length = _decode_length(data, position, SHORT_STRING, LONG_STRING)
    end = start + length
    if end > len(data):
        raise ValueError('RLP data is too short')
    if not is_list:
        if length == 1 and data[start] < SHORT_STRING:
            raise ValueError('RLP single byte below 0x80 must be encoded as itself')
        return data[start:end], end
    items = []
    while start < end:
        item, start = _decode_item(data, start)
        items.append(item)
    if start != end:
        raise ValueError('RLP list item is too short')
    return items, end


def decode(data: bytes) -> Item:
    """Decode the item, integers are returned as byte strings."""
    if not data:
        raise ValueError('RLP data is empty')
    item, end = _decode_item(data, 0)
    if end != len(data):
        raise ValueError('RLP data has bytes after the end of the item')
    return item
