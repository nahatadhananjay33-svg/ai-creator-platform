"""Launch target for accelerate: finetune_cli with a capped DataLoader.

f5_tts's finetune_cli calls ``trainer.train(train_dataset, resumable_with_seed=666)``
which silently uses the default ``num_workers=16``. Sixteen forked dataloader
workers exhaust Colab's 12.7 GB system RAM — observed 2026-07-17 as a SIGKILL
from the OOM killer at the epoch-2 boundary after a clean first epoch. The CLI
exposes no flag for it, so this shim patches the default before delegating.

Standalone on purpose (no repo imports): accelerate runs it as a plain script
inside the model venv. Worker count comes from ``F5_NUM_WORKERS`` (default 2).
"""
import os

from f5_tts.model import trainer as _trainer_mod

_orig_train = _trainer_mod.Trainer.train


def _train(self, train_dataset, num_workers=16, resumable_with_seed=None):
    capped = int(os.environ.get("F5_NUM_WORKERS", "2"))
    return _orig_train(self, train_dataset, num_workers=capped,
                       resumable_with_seed=resumable_with_seed)


_trainer_mod.Trainer.train = _train

from f5_tts.train import finetune_cli  # noqa: E402  (import after the patch)

if __name__ == "__main__":
    finetune_cli.main()
