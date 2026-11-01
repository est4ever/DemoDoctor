"""Download just ONE public robot video (~28 MB), not the entire dataset."""
from pathlib import Path
import shutil
from huggingface_hub import hf_hub_download

repo_id = "ankithreddy/so101_pickplace_uno"
filename = "videos/chunk-000/observation.images.images.top/episode_000000.mp4"
output = Path(__file__).parent / "sample_videos" / "sample.mp4"
output.parent.mkdir(parents=True, exist_ok=True)

print("Downloading one SO-101 top-camera episode from Hugging Face...")
source = hf_hub_download(repo_id=repo_id, filename=filename, repo_type="dataset")
shutil.copyfile(source, output)
print(f"Saved to: {output}")
