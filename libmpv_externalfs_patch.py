from pathlib import Path
import sys


def resolve_target() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser().resolve()

    cwd = Path.cwd()
    candidates = [
        cwd / 'src' / 'libmpv' / 'libmpv.cpp',
        cwd / 'libmpv-wasm-build' / 'src' / 'libmpv' / 'libmpv.cpp',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise SystemExit(
        'Could not locate libmpv.cpp. Pass the path explicitly, for example: '
        'python libmpv_externalfs_patch.py ./src/libmpv/libmpv.cpp'
    )


p = resolve_target()
text = p.read_text(encoding='utf-8', errors='ignore')

old = '''void open_disc_proxy(void* args) {
    filesystem::path path = *(string*)args;
    string root_name = *next(path.begin());
    string root_path = "/" + root_name;

    if (!filesystem::is_directory(root_path)) {
        printf("mounting directory at %s\\n", root_path.c_str());
        backend_t backend = wasmfs_create_externalfs_backend(root_name.c_str()); 
        int err = wasmfs_create_directory(root_path.c_str(), 0777, backend);     
        if (err) {
            fprintf(stderr, "Couldn't mount directory at %s\\n", root_path.c_str());
            return;
        }
    }

    if (!filesystem::is_directory(path)) {
        fprintf(stderr, "%s is not a directory\\n", path.c_str());
        return;
    }

    disc_info = open_bd_disc(path);
    free(args);
}

uint32_t open_disc(string path) {
'''

new = '''int ensure_externalfs_mount(const string& root_name) {
    string root_path = "/" + root_name;

    if (!filesystem::is_directory(root_path)) {
        printf("mounting directory at %s\\n", root_path.c_str());
        backend_t backend = wasmfs_create_externalfs_backend(root_name.c_str());
        int err = wasmfs_create_directory(root_path.c_str(), 0777, backend);
        if (err) {
            fprintf(stderr, "Couldn't mount directory at %s\\n", root_path.c_str());
            return err;
        }
    }

    return 0;
}

void open_disc_proxy(void* args) {
    filesystem::path path = *(string*)args;
    string root_name = *next(path.begin());

    if (ensure_externalfs_mount(root_name)) {
        return;
    }

    if (!filesystem::is_directory(path)) {
        fprintf(stderr, "%s is not a directory\\n", path.c_str());
        return;
    }

    disc_info = open_bd_disc(path);
    free(args);
}

int mount_externalfs_root(string root_name) {
    return ensure_externalfs_mount(root_name);
}

uint32_t open_disc(string path) {
'''

if old not in text:
    raise SystemExit('target block not found')
text = text.replace(old, new, 1)

old2 = '''    emscripten::function("loadFile", &load_file);
    emscripten::function("loadFiles", &load_files);
    // emscripten::function("loadUrl", &load_url);
'''
new2 = '''    emscripten::function("loadFile", &load_file);
    emscripten::function("loadFiles", &load_files);
    emscripten::function("mountExternalFsRoot", &mount_externalfs_root);
    // emscripten::function("loadUrl", &load_url);
'''
if old2 not in text:
    raise SystemExit('bindings block not found')
text = text.replace(old2, new2, 1)

p.write_text(text, encoding='utf-8')
print('patched libmpv.cpp')
