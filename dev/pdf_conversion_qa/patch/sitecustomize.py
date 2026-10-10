# INFRASTRUCTURE
import importlib.abc
import importlib.machinery
import inspect
import os
import sys
import textwrap

TARGET_MODULE = "mlx_vlm.tokenizer_utils"
TARGET_CLASS = "BPEStreamingDetokenizer"
TARGET_METHOD = "add_token"
OLD_EXPRESSION = '.decode("utf-8")'
NEW_EXPRESSION = '.decode("utf-8", errors="replace")'
MARKER_ENV = "QA_PATCH_MARKER"
ENABLE_ENV = "QA_DETOKENIZER_PATCH"


# ORCHESTRATOR
def install_patch() -> None:
    if os.environ.get(ENABLE_ENV) == "1":
        sys.meta_path.insert(0, DetokenizerPatchFinder())


# FUNCTIONS
class DetokenizerPatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != TARGET_MODULE:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        spec.loader = PatchingLoader(spec.loader)
        return spec


class PatchingLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def create_module(self, spec):
        return self.wrapped.create_module(spec)

    def exec_module(self, module):
        self.wrapped.exec_module(module)
        apply_patch(module)


def apply_patch(module) -> None:
    owner = getattr(module, TARGET_CLASS)
    original = getattr(owner, TARGET_METHOD)
    source = textwrap.dedent(inspect.getsource(original))
    if source.count(OLD_EXPRESSION) != 1:
        raise RuntimeError(f"detokenizer patch: expected exactly one {OLD_EXPRESSION!r} in {TARGET_METHOD}")
    namespace: dict = {}
    exec(compile(source.replace(OLD_EXPRESSION, NEW_EXPRESSION), module.__file__, "exec"), module.__dict__, namespace)
    setattr(owner, TARGET_METHOD, namespace[TARGET_METHOD])
    write_marker()


def write_marker() -> None:
    marker = os.environ.get(MARKER_ENV)
    if marker:
        with open(marker, "a") as handle:
            handle.write(f"{os.getpid()}\n")


install_patch()
