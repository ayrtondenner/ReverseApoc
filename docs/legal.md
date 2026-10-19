# Legal notes

This is a description of how the project handles copyrighted material, not legal advice.

## No game assets or code bytes in the repository

- No original executables, data files, CD images, extracted assets or disassembly are committed, now or later.
- Hashes (md5, SHA-1, CRC32) of the original files are committed. They identify the files without containing them.
- `.gitignore` and `.dockerignore` exclude `orig/`, `third_party/`, `asm/`, `build/`, `.env` and executable and image file types. Phase 1's gate checks that `git ls-files` contains no game file, no `.env` and no key.
- Never attach game files, executables or disassembly to issues or pull requests.

## You supply the game and the compiler

- **Game:** your own Steam or GOG copy. `uv run reverseapoc ingest` (Phase 2) copies the executables from the paths in your `.env` into the gitignored `orig/` and checks them against the hash manifest.
- **Compiler:** Watcom C/C++ 10.x and 11.0 is proprietary, and its current IP owner was not verified. The repository links to third-party archives and hosts no compiler bytes. `uv run reverseapoc fetch-watcom` is an opt-in convenience that you run on your own machine and at your own responsibility; nothing in the Dockerfile or CI runs it. The compiler lands in the gitignored `third_party/`, is mounted read-only into the container at run time, and is never baked into an image layer, so no image built from this repo carries it. Sources and commands: [Getting the Watcom compilers](toolchain.md#getting-the-watcom-compilers).
- Open Watcom v2 is redistributable under its own licence and is installed in the image, but only for auxiliary tools (`wdis`, `wlink`, `wlib`). It cannot produce matching code.

## Generated files stay local

`asm/` (disassembly) and `build/` (objects, rebuilt executables, reports) are regenerated on your machine from your own files and are gitignored. This follows KKND's `.gitignore` and Macabeus's script-generated Klonoa setup, and keeps the game's code bytes out of the repository.

## Licences in this repository

- **`tools/` is GPLv3** (version 3 or later). It includes modules copied from the [Theme Hospital decomp](https://github.com/matteo-pacini/theme-hospital-decomp) (`omf2elf.py` and related), whose tooling is GPLv3; their copyright headers are kept as-is. Code taken from [KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp) (CC0) and [retrokit](https://github.com/nemo22/retrokit) (Apache-2.0) can be combined into a GPLv3 work; the reverse is not possible.
- **decomp.wtf** (MIT) is a separate tool run as a subprocess in WSL2. It is never imported or vendored, so its code does not mix with ours.
- **Decompiled C under `src/` and `include/`:** this code reproduces the logic of the copyrighted original game. It is written for interoperability and research, and published to help OpenApoc, a GPL reimplementation that requires the original game files, understand the original behaviour. As with Theme Hospital's decomp, the project claims no rights in it, and it ships with no assets. Rebuilding the game from it requires your own original executables.

## AI use

AI tools, Claude Code in particular, are used openly for research, tooling and decompilation attempts. AI output is never trusted on its own: every match is accepted only after a deterministic byte comparison run by the build (objdiff, relocation checks, whole-EXE SHA-1), and the agent is blocked from editing the original files, hash manifests and build scripts.

## Why not IDA Free

IDA Free was rejected. Its decompiler runs in Hex-Rays' cloud, so function bytes would leave the machine, and the owner wants analysis to stay local. It also cannot load LE executables (its file formats are PE, ELF and Mach-O), has no IDAPython and is not supported by ida-pro-mcp. Ghidra with an LE loader runs fully locally.

## Community reception and our conduct

Parts of the decompilation community oppose AI-driven decompilation: decomp.wtf was archived and decomp.dev closed to new projects in October 2026, both citing AI-driven behaviour. Our conduct follows from that:

- State AI use openly (README and this file).
- Do not flood shared services such as decomp.me with agent-generated scratches; use them sparingly, by hand, for genuinely hard functions.
- Credit prior reverse engineering, especially OpenApoc's extractors and its contributors' Ghidra work, wherever it is reused.
- List the project in directories (recomp.fyi, decomphub.com) honestly as an AI-assisted decomp.
