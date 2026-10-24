// ExportDrafts.java: Ghidra decompile drafts for given function addresses (D-16).
// Written for this repo against the Ghidra 12.1.4 GhidraScript and decompiler API (Apache-2.0);
// this file is GPLv3 like the rest of tools/ (docs/legal.md).
//
// Usage (analyzeHeadless): -postScript ExportDrafts.java <out dir> 0x000XXXXX [0x000XXXXX ...]
// For each address it decompiles the function that starts there and writes
// <out dir>/func_XXXXXXXX.c holding Ghidra's C text. An address with no function, or a decompile
// that does not complete, writes nothing and prints the address. The drafts are a reading aid for
// the executor and never count as a match; reverseapoc.ghidra points <out dir> at the gitignored
// asm/<exe>/ghidra/ tree, so they are never committed.
//@category ReverseApoc

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class ExportDrafts extends GhidraScript {

	private static final int TIMEOUT_SECONDS = 120;

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 2) {
			throw new IllegalArgumentException(
				"usage: ExportDrafts.java <out dir> 0x000XXXXX [0x000XXXXX ...]");
		}
		File outDir = new File(args[0]);
		DecompInterface decomp = new DecompInterface();
		try {
			if (!decomp.openProgram(currentProgram)) {
				throw new IllegalStateException("decompiler: " + decomp.getLastMessage());
			}
			int written = 0;
			for (int i = 1; i < args.length; i++) {
				if (draft(decomp, outDir, args[i])) {
					written++;
				}
			}
			println("ExportDrafts: wrote " + written + " of " + (args.length - 1) + " drafts to "
				+ outDir);
		}
		finally {
			decomp.dispose();
		}
	}

	/** Decompile the function at `text` into outDir/func_XXXXXXXX.c; false when none is written. */
	private boolean draft(DecompInterface decomp, File outDir, String text) throws Exception {
		long offset = Long.parseLong(text.substring(2), 16);
		Address address = toAddr(offset);
		Function function = getFunctionAt(address);
		if (function == null) {
			println("ExportDrafts: no function at " + text);
			return false;
		}
		DecompileResults results = decomp.decompileFunction(function, TIMEOUT_SECONDS, monitor);
		if (!results.decompileCompleted() || results.getDecompiledFunction() == null) {
			println("ExportDrafts: decompile failed at " + text + ": " + results.getErrorMessage());
			return false;
		}
		File out = new File(outDir, String.format("func_%08X.c", offset));
		try (PrintWriter w = new PrintWriter(out, "UTF-8")) {
			w.print(results.getDecompiledFunction().getC());
		}
		return true;
	}
}
