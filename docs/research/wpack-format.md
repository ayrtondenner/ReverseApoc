# The Watcom 10.x wpack archive format

Watcom shipped parts of the 10.5 CD as `wpack` archives (`DISKIMGS/DISKnn/PCKnnnnn.k`). The real
10.5 compiler `BINW/WCC386.EXE` is one of them: the copy in `BINW/` on the disc is a damaged
65,536-byte stub. This note describes the archive format well enough to write a decoder from it.
It is the specification for `tools/reverseapoc/wpack.py` (decision D-15 in
`.planning/phases/04-compiler-identification/04-CONTEXT.md`): the decoder is written from this
text, not from any existing implementation.

Sources: Open Watcom v2 `bld/wpack` (`h/wpack.h`, `c/decode.c`, `c/common.c`, `c/wpackio.c`,
`c/wqsort.c`) at commit `4c245dddbf4d23262c51ba2b4b809c1b34a9fa86`, read as a format reference
only, and the measurements on the 10.5 disc recorded in `04-RESEARCH.md` ("Pattern 1: wpack
decoder", Pitfall 8). Where the 10.5 disc differs from Open Watcom v2, the disc wins and the
difference is called out.

All integers are little-endian and unaligned. "Bit stream" always means most significant bit
first: the first bit of the stream is bit 7 of the first byte.

## 1. Archive layout

An archive is three regions, back to back:

| Region | Offset | Content |
|---|---|---|
| Header | 0 | 12 bytes, section 2 |
| Compressed streams | 12 | one stream per member, in table order |
| File-info table | `info_offset` | `num_files` variable-length records, `info_len` bytes in total, section 3 |

The table sits at the end, after the data, so it is found through the header and not by
scanning.

### Archives split over several disks

A large archive is cut into parts named `.1`, `.2`, ... on consecutive install disks. The parts
are a plain byte concatenation of one archive: no per-part header, no padding, no overlap.
Joining them in order gives the archive. `PCK00017` proves it: `PCK00017.1` (109,568 bytes) plus
`PCK00017.2` (247,871 bytes) is 357,439 bytes, which is exactly `info_offset` (357,412) plus
`info_len` (27).

## 2. Header (12 bytes on the 10.5 disc)

| Offset | Size | Field | Value on the 10.5 disc |
|---:|---:|---|---|
| 0 | 2 | signature | `0x2403` (bytes `03 24`) |
| 2 | 1 | major version | 1 |
| 3 | 1 | minor version | 1 |
| 4 | 2 | number of members (`num_files`) | 1 for `PCK00017` |
| 6 | 2 | length of the file-info table (`info_len`) | 27 for `PCK00017` |
| 8 | 4 | offset of the file-info table (`info_offset`) | 357,412 for `PCK00017` |

Open Watcom v2 declares a 16-byte header with a fourth 32-bit field after `info_offset` (an
access key for "secure" archives). **The 10.5 archives do not have it.** The proof is the first
member's `disk_addr`, which is 12: its compressed stream begins right after a 12-byte header. A
decoder that assumes 16 bytes starts every stream four bytes late and decodes garbage (Pitfall 8).

A reader should therefore check that the first member's `disk_addr` equals the 12-byte header
size and refuse the archive otherwise; that check is what tells this layout apart from the
16-byte one.

## 3. File-info table

`num_files` records, one per member, packed with no padding. Record size is 17 bytes plus the
name length.

| Offset | Size | Field | Meaning |
|---:|---:|---|---|
| 0 | 4 | length | uncompressed size of the member in bytes |
| 4 | 4 | disk_addr | archive offset of the member's compressed stream |
| 8 | 4 | stamp | DOS-era time stamp of the original file (not needed to decode) |
| 12 | 4 | crc | CRC-32 of the member's compressed stream, section 4 |
| 16 | 1 | namelen | bits 0-6: name length; bit 7 (`0x80`): the stream has **no Shannon code** |
| 17 | namelen & 0x7F | name | file name, ASCII, no terminator |

`PCK00017` has one record: name `wcc386.exe` (10 bytes, so the record is 27 bytes, which is
`info_len`), length 567,558, `disk_addr` 12, Shannon-coded (bit 7 clear).

Bit 7 of `namelen` selects the stream format: clear means a Shannon-coded stream (section 7),
set means the simpler "no Shannon" stream (section 6).

Member names are matched without regard to case (they are DOS file names). A decoder never needs
to use a name as a path; it returns bytes.

## 4. Member extent and CRC

A member's compressed stream runs from its `disk_addr` to the next member's `disk_addr`, or to
`info_offset` for the last member. The streams appear in table order, so `disk_addr` never
decreases from one record to the next, and every stream lies inside
`[12, info_offset)`.

The `crc` field is the standard CRC-32 (the reflected polynomial `0xEDB88320`, initial value and
final complement `0xFFFFFFFF`, the same function as `zlib.crc32`) of the **compressed** bytes of
that extent. For `PCK00017`, CRC-32 of archive bytes `[12, 357412)` equals the stored `crc`. The
check runs before any decoding, so a damaged or truncated archive is refused before it costs
anything.

The original tool computed the CRC on the fly over exactly the bytes its decoder consumed and
gave back its read-ahead; computing it over the extent is the same thing for a well-formed
archive.

## 5. The sliding window (shared by both stream formats)

Both formats are LZSS over a 4,096-byte ring buffer:

| Parameter | Value |
|---|---|
| Window size | 4,096 bytes |
| Look-ahead size | 60 bytes (the longest match) |
| Threshold | 2 (matches are at least 3 bytes in the Shannon format) |
| Initial write position | 4,096 - 60 = 4,036 |
| Initial content | ring positions 0 to 4,035 hold a space (`0x20`); positions 4,036 to 4,095 are never written before use and hold `0x00` in a fresh decoder |

Each output byte is also written into the ring at the write position, which then advances by one
modulo 4,096.

A match is a pair (length, position). The source of the copy is ring position
`(write position - position - 1) mod 4096`, and the bytes are copied one at a time, each copied
byte going both to the output and into the ring before the next one is read. A match may
therefore overlap the bytes it is producing (a short pattern repeated).

An equivalent view that needs no ring: the match copies from `position + 1` bytes back in the
output stream. If that reaches before the first output byte, it reads the initial window
content. Laid out in output order, the 4,096 bytes that precede the first output byte are 60
bytes of `0x00` followed by 4,036 spaces.

### Match positions (both formats)

A position is a 12-bit number (0 to 4,095). Its upper 6 bits are coded with a variable-length
code, its lower 6 bits are sent raw. Decoding uses two 256-entry tables indexed by the next 8
bits of the bit stream: `D_CODE` gives the upper 6 bits, `D_LEN` the total code length in bits
(3 to 8) of the upper part. These are the classic LZHUF tables (Haruyasu Yoshizaki's 1988 LZHUF,
after Haruhiko Okumura's LZSS), reproduced in the decoder as data.

Steps:

1. Read the next 8 bits as `i`.
2. The upper 6 bits are `D_CODE[i]`.
3. Read `D_LEN[i] - 2` more bits (1 to 6) and append them below `i`.
4. The lower 6 bits are the low 6 bits of that combined value.
5. Position = upper × 64 + lower.

So the variable-length prefix and the 6 raw bits are read as one run of `D_LEN[i] + 6` bits;
`D_LEN` says how many of the 8 bits already read belong to the prefix.

Both tables are runs of equal values over increasing `i`, and their runs line up (index ranges
are inclusive):

| `i` range | Indices | `D_CODE[i]` | Indices per `D_CODE` value | `D_LEN[i]` |
|---|---:|---|---:|---:|
| 0x00-0x1F | 32 | 0 | 32 | 3 |
| 0x20-0x4F | 48 | 1 to 3 | 16 | 4 |
| 0x50-0x8F | 64 | 4 to 11 | 8 | 5 |
| 0x90-0xBF | 48 | 12 to 23 | 4 | 6 |
| 0xC0-0xEF | 48 | 24 to 47 | 2 | 7 |
| 0xF0-0xFF | 16 | 48 to 63 | 1 | 8 |

Within a row, `D_CODE` increases by one every "indices per value" entries, starting at the
row's first value. Example: `i = 0x93` is in the fourth row, so `D_CODE = 12 + (0x93 - 0x90) / 4`
(integer division) = 12 and `D_LEN = 6`.

## 6. "No Shannon" stream (`namelen` bit 7 set)

A pure bit stream that starts at the first byte of the member's extent. Tokens repeat until the
output holds `length` bytes:

| First bit | Then | Meaning |
|---|---|---|
| 0 | 8 bits | a literal byte |
| 1 | 6 bits `n`, then a position (section 5) | copy `n` bytes from the window |

Here `n` is the copy count itself (no threshold is added). A token never straddles the end of
the member's output in a well-formed stream; a decoder should refuse a match that would write
past `length`, and a stream that runs out of bits before `length` bytes are produced.

## 7. Shannon-coded stream (`namelen` bit 7 clear)

The stream starts with a code-length table (whole bytes), followed by a bit stream of coded
symbols.

### 7.1 Symbols

There are 314 symbols (256 - threshold 2 + look-ahead 60):

- 0 to 255: a literal byte with that value.
- 256 to 313: a match of length `symbol - 253` (3 to 60 bytes); a position (section 5) follows.

### 7.2 The run-length packed code-length table

Byte-aligned, at the start of the extent.

1. The first byte is the number of entries minus one (1 to 256 entries).
2. Each entry is one byte. A running symbol counter starts at 0.
   - Bit 7 set: skip. The next `(entry & 0x7F) + 1` symbols get no code. The counter advances by
     that many.
   - Bit 7 clear: a run. The next `(entry >> 4) + 1` symbols (1 to 8) all get code length
     `(entry & 0x0F) + 1` (1 to 16 bits). The counter advances by that many.
3. Symbols the table never reaches get no code.

A table whose runs and skips push the counter past 314 is malformed. The coded symbols are
listed in increasing symbol order as they are read; call that list the *index list*.

### 7.3 Canonical code assignment, and why the sort order matters

Codes are assigned in a canonical way from the lengths, but the order of symbols that share a
length is decided by **the sort that the original tool used**, not by the symbol value:

1. Sort the index list by code length, shortest first, using Watcom's C library `qsort`
   (section 8). It is not a stable sort, and the decoder must reproduce its exact permutation of
   equal-length symbols. A stable sort gives a different code assignment and a garbage output
   (on `PCK00017`: no `MZ` header).
2. Walk the sorted list **from the last element to the first** (longest codes first). Keep a
   16-bit code value, starting at 0. For each element, first add the step of the previous
   element (0 for the first one), then hand the current value to this symbol. The step for a
   code of length `L` is `2^(16 - L)`: code values are left-aligned in 16 bits. All arithmetic
   is modulo 2^16.
3. For each length `L` record the first code value handed out at that length (`first[L]`, the
   smallest value of that length) and where that length's symbols start in the walk order
   (`offset[L]`). Lengths with no symbols get `first[L] = 0xFFFF`.
4. Keep the walk order itself as the symbol map: element `k` of the walk is the symbol with the
   `k`-th code.

The result: longer codes have smaller values; within a length, codes increase in walk order,
which is the reverse of the sorted order.

### 7.4 Decoding a symbol

1. Look at the next 16 bits of the bit stream without consuming them (bits past the end of the
   extent read as 0 for this look-ahead only), as a 16-bit number `v`.
2. Starting at the shortest code length present and going up, take the first length `L` with
   `v >= first[L]`.
3. The symbol is the map entry at `offset[L] + ((v - first[L]) >> (16 - L))`.
4. Consume `L` bits.

Because the comparison is "greater or equal" and absent lengths have `first = 0xFFFF`, an absent
length is never chosen once a shorter present length has matched. A result index outside the
map, or no matching length up to 16, means a corrupt stream.

Since each decision depends only on `v`, the whole lookup can be precomputed into a 65,536-entry
table from `v` to (symbol, length).

### 7.5 The loop

Repeat until the output holds `length` bytes: decode a symbol; a literal goes to the output and
the window; a match symbol is followed by a position (section 5) and copies `symbol - 253`
bytes. Refuse a match that would write past `length` and a stream that runs out of bits.

## 8. Watcom C library `qsort`: the exact order of equal keys

The original tool sorts the index list with a private copy of the Watcom C library `qsort`
(kept in the tool precisely because the archive format depends on its tie behaviour). The
elements are machine words, so the pivot is held as a value outside the array rather than
swapped to the front. The comparison is "code length of left minus code length of right"; only
its sign matters. What follows is the algorithm in prose; an implementation must follow it step
by step, because every swap decides where equal keys end up.

The sort works on a sub-array (start, count) and keeps a stack of sub-arrays still to sort. It
starts with the whole array.

### 8.1 Fewer than 16 elements: a two-pass shell sort

Two passes, gap 3 and then gap 1. In each pass, visit the positions `gap, 2·gap, 3·gap, ...`
(relative to the sub-array start) that lie inside the sub-array. For each visited position,
move its element backwards in steps of `gap` by repeated swapping, while the element `gap`
places before it compares strictly greater.

Note the quirk: in the gap-3 pass only positions that are multiples of 3 are visited, so only
the chain 0, 3, 6, 9, 12 is sorted; elements at positions 1, 2, 4, 5, ... are not touched by
that pass. The gap-1 pass is a plain insertion sort over every position, so the result is fully
sorted. Insertion with a strict comparison never reorders equal keys, so the tie order comes
only from the gap-3 pass.

Worked example (keys only, letters tag equal keys): `[2a, 1a, 1b, 1c, 2b, 1d]`. Gap 3 visits
position 3 only (position 6 is outside): `1c` is less than `2a`, so they swap:
`[1c, 1a, 1b, 2a, 2b, 1d]`. Gap 1 then insertion-sorts: `1d` moves in front of `2b` and `2a`:
`[1c, 1a, 1b, 1d, 2a, 2b]`. A stable sort would give `[1a, 1b, 1c, 1d, 2a, 2b]`.

A sub-array with fewer than 16 elements is finished after these two passes.

### 8.2 16 elements or more: three-way partition

1. **Pivot choice.** Let `n` be the count and `mid` the element at index `n / 2` (integer
   division). For `n` of 30 or more, let `lo` be the first and `hi` the last element; for `n` of
   43 or more first refine all three with a step `s = n / 8`: `lo` becomes the median of the
   elements at `0, s, 2s`; `mid` becomes the median of `mid - s, mid, mid + s`; `hi` becomes the
   median of `n - 1 - 2s, n - 1 - s, n - 1`. Then (for `n` of 30 or more) `mid` becomes the
   median of `lo, mid, hi`. For 16 to 29 elements the middle element is used as is. The pivot
   value is a copy of the chosen element; the array is not changed by the choice.

   The median of three `(a, b, c)` is chosen with this exact sequence of comparisons (it decides
   which of several equal elements is picked, which matters only through its value here, but is
   kept exact):
   - if `a > b`: if `a > c`, the result is `b` when `b > c`, else `c`; otherwise (`a <= c`) the
     result is `a`.
   - otherwise (`a <= b`): if `a >= c`, the result is `a`; otherwise the result is `c` when
     `b > c`, else `b`.

2. **Partition.** Four cursors: `pa` and `pb` start at the first element, `pc` and `pd` at the
   last. Repeat:
   - While `pb <= pc` and the element at `pb` is not greater than the pivot: if it is equal,
     swap it with the element at `pa` and advance `pa`. Advance `pb`.
   - While `pc >= pb` and the element at `pc` is not less than the pivot: if it is equal, swap it
     with the element at `pd` and step `pd` back. Step `pc` back.
   - If `pb > pc`, stop. Otherwise swap the elements at `pb` and `pc`, advance `pb`, step `pc`
     back, and repeat.

   Equal keys collect at both ends (`[start, pa)` and `(pd, end]`), smaller keys in `[pa, pb)`,
   larger keys in `(pc, pd]`.

3. **Bring the equal keys to the middle.** Let `end` be one past the last element.
   - `s = min(pa - start, pb - pa)`. Swap the `s` elements starting at `start` pairwise with the
     `s` elements ending just before `pb` (first with first, second with second, ...).
   - `s = min(pd - pc, end - pd - 1)`. Swap the `s` elements starting at `pb` pairwise with the
     `s` elements ending just before `end`.

   Now the smaller keys occupy the first `r = pb - pa` elements, the larger keys the last
   `t = pd - pc` elements, and the equal keys sit between them, finished.

4. **Recurse without recursion.** If `t >= r`: push the larger-keys block (its start is
   `end - t`, count `t`) on the stack and continue with the smaller-keys block (same start,
   count `r`). Otherwise: if `r <= 1` the sub-array is done; else push the smaller-keys block
   (start, `r`) and continue with the larger-keys block (`end - t`, `t`).

5. When the current sub-array has fewer than two elements, or a shell-sorted one is finished,
   pop the next sub-array from the stack; stop when the stack is empty.

An index list of 16 or more coded symbols (as in any real archive member) takes this path at
the top level, so its code assignment depends on the partition steps as well as on the shell
sort used for the small blocks.

## 9. `PCK00017` facts

| Fact | Value |
|---|---|
| Parts | `DISKIMGS/DISK02/PCK00017.1` (109,568 bytes), `DISKIMGS/DISK03/PCK00017.2` (247,871 bytes) on the 10.5 CD |
| Joined size | 357,439 bytes |
| Header | signature `0x2403`, version 1.1, 1 member, `info_len` 27, `info_offset` 357,412 |
| Member | `wcc386.exe`, length 567,558, `disk_addr` 12, Shannon-coded |
| CRC check | CRC-32 of bytes `[12, 357412)` equals the member's `crc` |
| Decoded file | the 10.5 `BINW/WCC386.EXE`: an MZ program carrying an LE image |

The decoded size and hashes are pinned in `config/watcom.toml` by plan 04-06 after an end-to-end
`install-watcom 10.5`, not here.

## Licence note

Open Watcom's `bld/wpack` is under the Sybase Open Watcom Public License 1.0, which is not
compatible with the GPLv3 that covers `tools/`. It is cited here as the format reference only.
This document describes the format in prose and tables; no Open Watcom source code or comments
are reproduced here or in `tools/reverseapoc/wpack.py`. The `D_CODE`/`D_LEN` position tables are
the classic 1988 LZHUF tables (Haruyasu Yoshizaki, after Haruhiko Okumura's LZSS), which are
reused as data.
