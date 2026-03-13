#!/usr/bin/env python3
"""
Patch mount_externalfs_root() to proxy execution to side_thread,
so wasmfs_create_externalfs_backend() is called off the main browser thread.
Uses dynamic line search — robust to prior edits.
"""
import subprocess

TARGET = "/home/ubuntu/Others/libmpv-wasm-build/src/libmpv/libmpv.cpp"

with open(TARGET, "r") as f:
    lines = f.readlines()

print(f"File has {len(lines)} lines")

def find_line(marker, start=0):
    for i in range(start, len(lines)):
        if marker in lines[i]:
            return i
    raise ValueError(f"Marker not found: {marker!r}")

# Guard: don't patch twice
if any("mount_externalfs_proxy" in l for l in lines):
    print("Already patched with proxy. Aborting.")
    exit(0)

# ── Locate the current mount_externalfs_root function ────────────────────────
mount_fn_idx = find_line("int mount_externalfs_root(string root_name)")
print(f"mount_externalfs_root at line {mount_fn_idx+1}: {lines[mount_fn_idx]!r}")

# It's currently 3 lines:
#   int mount_externalfs_root(string root_name) {
#       return ensure_externalfs_mount(root_name);
#   }
assert "return ensure_externalfs_mount" in lines[mount_fn_idx + 1], \
    f"Unexpected line +1: {lines[mount_fn_idx+1]!r}"
assert lines[mount_fn_idx + 2].strip() == "}", \
    f"Unexpected line +2: {lines[mount_fn_idx+2]!r}"

# Replace those 3 lines with the proxy version
new_mount_block = [
    "// Proxy args: pass root_name string to side_thread for WasmFS mount\n",
    "struct mount_externalfs_args_t {\n",
    "    string root_name;\n",
    "    int result;\n",
    "};\n",
    "\n",
    "void mount_externalfs_proxy(void* args) {\n",
    "    mount_externalfs_args_t* a = (mount_externalfs_args_t*)args;\n",
    "    a->result = ensure_externalfs_mount(a->root_name);\n",
    "}\n",
    "\n",
    "// JS-callable: proxy to side_thread (WasmFS requires off-main-thread)\n",
    "int mount_externalfs_root(string root_name) {\n",
    "    mount_externalfs_args_t* args = new mount_externalfs_args_t{root_name, -1};\n",
    "    emscripten_proxy_sync(main_queue, side_thread, mount_externalfs_proxy, args);\n",
    "    int err = args->result;\n",
    "    delete args;\n",
    "    return err;\n",
    "}\n",
]

lines[mount_fn_idx:mount_fn_idx + 3] = new_mount_block
print(f"Replaced mount_externalfs_root ({3} lines) with proxy version ({len(new_mount_block)} lines)")

with open(TARGET, "w") as f:
    f.writelines(lines)

print("Done. Verifying:")
result = subprocess.run(
    ["grep", "-n", "mount_externalfs_proxy\|mount_externalfs_root\|emscripten_proxy_sync", TARGET],
    capture_output=True, text=True
)
print(result.stdout)
