// ExportFunctions.java: headless Ghidra export of function entries, bodies and names (SPL-01, D-05).
// Written for this repo against the Ghidra 12.1.4 GhidraScript API (Apache-2.0); this file is
// GPLv3 like the rest of tools/ (docs/legal.md).
//
// Usage (analyzeHeadless): -postScript ExportFunctions.java <out csv>
// Writes a header and one CSV row per function:
//   entry,body_min,body_max,addresses,ranges,thunk,calling_convention,name
// with addresses as 0x%08X. It writes addresses and names only: never bytes, instructions or
// relocations. Target bytes and fixups come from le.py alone (P4). reverseapoc.ghidra reads it.
//@category ReverseApoc

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;

public class ExportFunctions extends GhidraScript {

	private static final String HEADER =
		"entry,body_min,body_max,addresses,ranges,thunk,calling_convention,name";

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 1) {
			throw new IllegalArgumentException("usage: ExportFunctions.java <out csv>");
		}
		int count = 0;
		try (PrintWriter out = new PrintWriter(new File(args[0]), "UTF-8")) {
			out.print(HEADER + "\n");
			for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
				out.print(row(f) + "\n");
				count++;
			}
		}
		println("ExportFunctions: wrote " + count + " functions to " + args[0]);
	}

	private static String row(Function f) {
		AddressSetView body = f.getBody();
		int ranges = 0;
		for (AddressRange ignored : body) {
			ranges++;
		}
		return hex(f.getEntryPoint().getOffset()) + "," + hex(body.getMinAddress().getOffset())
			+ "," + hex(body.getMaxAddress().getOffset()) + "," + body.getNumAddresses() + ","
			+ ranges + "," + f.isThunk() + "," + cell(f.getCallingConventionName()) + ","
			+ cell(f.getName());
	}

	private static String hex(long offset) {
		return String.format("0x%08X", offset);
	}

	/** One CSV cell: quoted (with doubled quotes) when it holds a comma, quote or line break. */
	private static String cell(String text) {
		String value = text == null ? "" : text;
		if (value.contains(",") || value.contains("\"") || value.contains("\n")
			|| value.contains("\r")) {
			return "\"" + value.replace("\"", "\"\"") + "\"";
		}
		return value;
	}
}
