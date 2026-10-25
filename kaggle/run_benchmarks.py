# Kaggle notebook source (same cells as kaggle/run_benchmarks.ipynb).
# Settings: Accelerator = GPU T4 x2, Internet = On.  Add-ons -> Secrets: HF_TOKEN (+ GH_TOKEN if the repo is private).
# Checkpoint run: BENCHES = ["smoke"] in an interactive session.
# Full run: BENCHES = ["pope", "chair"], then Save Version -> "Save & Run All (Commit)".

# %% 1. Secrets, clone
import os, subprocess, sys
from kaggle_secrets import UserSecretsClient

BENCHES = ["pope", "chair"]            # ["smoke"] for the checkpoint run
REPO_URL = "github.com/Kavyaansh-28/vlm_toolkit.git"
BRANCH = "main"
RESULTS_REPO = "vlm-reliability-pccoe/vlm-results"

secrets = UserSecretsClient()
os.environ["HF_TOKEN"] = secrets.get_secret("HF_TOKEN")
try:
    token = secrets.get_secret("GH_TOKEN") + "@"
except Exception:
    token = ""  # public repository
os.environ["RESULTS_REPO"] = RESULTS_REPO
os.environ["VLM_HARDWARE"] = "kaggle:t4"
if not os.path.exists("/kaggle/working/vlm"):
    subprocess.run(["git", "clone", "--depth", "1", "-b", BRANCH, f"https://{token}{REPO_URL}", "/kaggle/working/vlm"], check=True)
os.chdir("/kaggle/working/vlm")
subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"])

# %% 2. Install (keeps Kaggle's CUDA torch) and pull partial results for resume
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt", "-r", "requirements-cuda.txt"], check=True)
subprocess.run([sys.executable, "-m", "evaluation.hub_sync", "pull", "--repo", RESULTS_REPO])

# %% 3. Data and model weights ONCE, before the parallel processes start
if BENCHES == ["smoke"]:
    subprocess.run([sys.executable, "-m", "evaluation.prepare_data", "--out", "data/smoke", "--only", "smoke"], check=True)
else:
    subprocess.run([sys.executable, "-m", "evaluation.prepare_data", "--out", "data/benchmarks", "--pope-images", "450",
                    "--chair-images", "500", "--tune-images", "50", "--seed", "42"], check=True)
from huggingface_hub import snapshot_download
for model in ["llava-hf/llava-1.5-7b-hf", "IDEA-Research/grounding-dino-tiny", "openai/clip-vit-base-patch32"]:
    snapshot_download(model)

# %% 4. POPE on GPU 0 and CHAIR on GPU 1, in parallel
procs = []
for gpu, bench in enumerate(BENCHES):
    log = open(f"/kaggle/working/{bench}.log", "w")
    procs.append((bench, subprocess.Popen(["bash", "jobs/run_eval.sh", bench], stdout=log, stderr=subprocess.STDOUT,
                                          env={**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)})))
for bench, proc in procs:
    print(bench, "exit code", proc.wait())
subprocess.run("tail -n 25 /kaggle/working/*.log", shell=True)

# %% 5. Report (also copied to /kaggle/working as notebook output)
if BENCHES != ["smoke"]:
    subprocess.run([sys.executable, "-m", "evaluation.run_benchmarks", "--proc", "results/proc",
                    "--out", "results/benchmark_report.json", "--markdown", "results/RESULTS.md"])
    subprocess.run([sys.executable, "-m", "evaluation.hub_sync", "push", "--repo", RESULTS_REPO,
                    "--patterns", "results/benchmark_report.json", "results/RESULTS.md"])
    print(open("results/RESULTS.md").read())
subprocess.run("cp -r results /kaggle/working/results_copy", shell=True)
