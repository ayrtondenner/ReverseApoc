# Phase 05: API coverage

No external API integration: Phase 05 builds a local matching pipeline (omf2elf, target ELF writer, relocation check, splice, configure/ninja) around local tools run as subprocesses or libraries (Ghidra 12.1.4 headless and its GhidraScript Java API inside the container, objdiff-cli, wcc386 under wibo, clang, the capstone Python binding); the detector's one hit ("Ghidra API", 05-10-PLAN.md) names the scripting API of a locally installed program, not a network service or SDK integration.
