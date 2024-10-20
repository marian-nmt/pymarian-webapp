import os

QUIET = os.getenv('MARIAN_QUIET', "").lower() in ("1", "yes", "y", "true", "on")
CPU_THREADS = int(os.getenv('MARIAN_CPU_THREADS', "4"))
WORKSPACE_MEMORY = int(os.getenv('MARIAN_WORKSPACE_MEMORY', "6000"))
DEF_EAGER_LOAD = False

BASE_ARGS = dict(
    mini_batch=8,
    maxi_batch=64,
    cpu_threads=CPU_THREADS,
    workspace=WORKSPACE_MEMORY,
    quiet=QUIET,
)

DEF_FLICKER_SIZE = 4  # tokens

# make these metrics available by default
CHOSEN_METRICS = ["wmt20-comet-qe-da", "wmt22-cometkiwi-da", "wmt23-cometkiwi-da-xl"]