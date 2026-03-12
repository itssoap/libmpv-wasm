#!/usr/bin/env python3
"""
Line-indexed patcher for libmpv.cpp.
Inserts mountExternalFsRoot binding and helper functions.
Uses dynamic line search (not hardcoded indices) to be robust.
"""

import subprocess

TARGET = "/home/ubuntu/Others/libmpv-wasm-build/src/libmpv/libmpv.cpp"

with open(TARGET, "r") as f:
    lines = f.readlines()

total = len(lines)
print(f"File has {total} lines")

def find_line(marker, start=0):
    for i in range(start, len(lines)):
        if marker in lines[i]:
            return i
    raise ValueError(f"Marker not found: {marker!r}")

# ── Locate key positions ───────────────────────────────────────────────────────
open_disc_proxy_idx = find_line("void open_disc_proxy")
open_disc_idx       = find_line("uint32_t open_disc")
bindings_idx        = find_line("EMSCRIPTEN_BINDINGS")
loadfiles_idx       = find_line('emscripten::function("loadFiles"')

print(f"open_disc_proxy at line {open_disc_proxy_idx+1}")
print(f"open_disc       at line {open_disc_idx+1}")
print(f"EMSCRIPTEN_BINDINGS at line {bindings_idx+1}")
print(f"loadFiles       at line {loadfiles_idx+1}")

# Guard: don't patch twice
if any("mount_externalfs_root" in l for l in lines):
    print("Already patched! Aborting.")
    exit(0)

# ── 1. Insert helper functions before open_disc_proxy ─────────────────────────
ensure_block = [
    "// Helper: mount a named ExternalFS root (idempotent)\n",
    "static int ensure_externalfs_mount(const std::string& root_name) {\n",
    '    std::string root_path = "/" + root_name;\n',
    "    if (!filesystem::is_directory(root_path)) {\n",
    '        printf("mounting externalfs at %s\\n", root_path.c_str());\n',
    "        backend_t backend = wasmfs_create_externalfs_backend(root_name.c_str());\n",
    "        int err = wasmfs_create_directory(root_path.c_str(), 0777, backend);\n",
    "        if (err) {\n",
    '            fprintf(stderr, "Couldn\'t mount externalfs at %s\\n", root_path.c_str());\n',
    "            return err;\n",
    "        }\n",
    "    }\n",
    "    return 0;\n",
    "}\n",
    "\n",
    "// JS-callable: mount a named ExternalFS root and return errno (0 = ok)\n",
    "int mount_externalfs_root(string root_name) {\n",
    "    return ensure_externalfs_mount(root_name);\n",
    "}\n",
    "\n",
]

lines[open_disc_proxy_idx:open_disc_proxy_idx] = ensure_block
print(f"Inserted {len(ensure_block)} lines of helper functions before open_disc_proxy")

# ── Re-locate all positions after insertion ────────────────────────────────────
open_disc_proxy_idx = find_line("void open_disc_proxy")
open_disc_idx       = find_line("uint32_t open_disc")
bindings_idx        = find_line("EMSCRIPTEN_BINDINGS")
loadfiles_idx       = find_line('emscripten::function("loadFiles"')

print(f"After insert: open_disc_proxy at line {open_disc_proxy_idx+1}, bindings at line {bindings_idx+1}")

# ── 2. Refactor open_disc_proxy to use ensure_externalfs_mount ────────────────
# Locate the block inside open_disc_proxy that we want to replace:
#   "    string root_path = ..." through closing "    }" of the is_directory block
root_path_idx = find_line('string root_path = "/" + root_name', open_disc_proxy_idx)
print(f"root_path line at {root_path_idx+1}: {lines[root_path_idx]!r}")

# Find the closing brace of the if (!filesystem::is_directory(root_path)) block
# It's the first "    }" after the if block opens
is_dir_if_idx = find_line("if (!filesystem::is_directory(root_path))", root_path_idx)
print(f"is_directory if at line {is_dir_if_idx+1}")

# Walk forward to find the matching closing brace (depth 1 relative to function body)
depth = 0
close_idx = is_dir_if_idx
for i in range(is_dir_if_idx, open_disc_idx):
    stripped = lines[i].strip()
    if stripped == '{' or stripped.endswith('{'):
        depth += 1
    if stripped == '}' or stripped == '};':
        depth -= 1
        if depth == 0:
            close_idx = i
            break

print(f"Closing brace of if-block at line {close_idx+1}: {lines[close_idx]!r}")

# Lines to remove: root_path declaration, blank line, entire if-block
# root_path_idx .. close_idx inclusive, plus the blank line before if (root_path_idx+1 if blank)
blank_between = (lines[root_path_idx + 1].strip() == "")
remove_start = root_path_idx
remove_end   = close_idx + 1  # exclusive

print(f"Removing lines {remove_start+1}–{remove_end} ({remove_end - remove_start} lines)")
for i in range(remove_start, remove_end):
    print(f"  [{i+1}] {lines[i]!r}")

replacement = [
    "    if (ensure_externalfs_mount(*next(path.begin()))) {\n",
    "        free(args);\n",
    "        return;\n",
    "    }\n",
]

lines[remove_start:remove_end] = replacement
print(f"Replaced with {len(replacement)} lines")

# ── Re-locate bindings after second edit ──────────────────────────────────────
loadfiles_idx = find_line('emscripten::function("loadFiles"')
print(f"loadFiles now at line {loadfiles_idx+1}")

# ── 3. Add mountExternalFsRoot binding after loadFiles ────────────────────────
binding_line = '    emscripten::function("mountExternalFsRoot", &mount_externalfs_root);\n'
lines.insert(loadfiles_idx + 1, binding_line)
print(f"Inserted mountExternalFsRoot binding at line {loadfiles_idx+2}")

# ── Write back ────────────────────────────────────────────────────────────────
with open(TARGET, "w") as f:
    f.writelines(lines)

print("\nDone. Verifying:")
result = subprocess.run(
    ["grep", "-n",
     "mountExternalFsRoot\\|mount_externalfs_root\\|ensure_externalfs_mount",
     TARGET],
    capture_output=True, text=True
)
print(result.stdout)
print("Final line count:", len(lines))
