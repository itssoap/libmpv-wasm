from pathlib import Path

p = Path('src/libmpv/libmpv.cpp')
text = p.read_text(encoding='utf-8', errors='ignore')

if 'int ensure_externalfs_mount(const string& root_name)' not in text:
    text = text.replace(
        """void open_disc_proxy(void* args) {\n    filesystem::path path = *(string*)args;\n    string root_name = *next(path.begin());\n    string root_path = \"/\" + root_name;\n""",
        """int ensure_externalfs_mount(const string& root_name) {\n    string root_path = \"/\" + root_name;\n\n    if (!filesystem::is_directory(root_path)) {\n        printf(\"mounting directory at %s\\n\", root_path.c_str());\n        backend_t backend = wasmfs_create_externalfs_backend(root_name.c_str());\n        int err = wasmfs_create_directory(root_path.c_str(), 0777, backend);\n        if (err) {\n            fprintf(stderr, \"Couldn't mount directory at %s\\n\", root_path.c_str());\n            return err;\n        }\n    }\n\n    return 0;\n}\n\nvoid open_disc_proxy(void* args) {\n    filesystem::path path = *(string*)args;\n    string root_name = *next(path.begin());\n""",
        1,
    )

old_mount_block = """    string root_path = \"/\" + root_name;\n\n    if (!filesystem::is_directory(root_path)) {\n        printf(\"mounting directory at %s\\n\", root_path.c_str());\n        backend_t backend = wasmfs_create_externalfs_backend(root_name.c_str()); \n        int err = wasmfs_create_directory(root_path.c_str(), 0777, backend);     \n        if (err) {\n            fprintf(stderr, \"Couldn't mount directory at %s\\n\", root_path.c_str());\n            return;\n        }\n    }\n"""
new_mount_block = """    if (ensure_externalfs_mount(root_name)) {\n        return;\n    }\n"""
if old_mount_block in text:
    text = text.replace(old_mount_block, new_mount_block, 1)
else:
    raise SystemExit('mount block not found')

if 'int mount_externalfs_root(string root_name)' not in text:
    text = text.replace(
        """uint32_t open_disc(string path) {\n""",
        """int mount_externalfs_root(string root_name) {\n    return ensure_externalfs_mount(root_name);\n}\n\nuint32_t open_disc(string path) {\n""",
        1,
    )

if 'emscripten::function("mountExternalFsRoot", &mount_externalfs_root);' not in text:
    text = text.replace(
        """    emscripten::function(\"loadFile\", &load_file);\n    emscripten::function(\"loadFiles\", &load_files);\n    // emscripten::function(\"loadUrl\", &load_url);\n""",
        """    emscripten::function(\"loadFile\", &load_file);\n    emscripten::function(\"loadFiles\", &load_files);\n    emscripten::function(\"mountExternalFsRoot\", &mount_externalfs_root);\n    // emscripten::function(\"loadUrl\", &load_url);\n""",
        1,
    )

p.write_text(text, encoding='utf-8')
print('patched libmpv.cpp')
