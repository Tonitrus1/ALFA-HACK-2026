"""CPU-only E5 implementation; model/tokenizer never access the network here."""
import os
from pathlib import Path
from threading import Lock

import numpy as np


class E5Encoder:
    def __init__(self, path: Path, threads: int = 4):
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(threads)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(path), local_files_only=True,
                                              use_safetensors=True).to('cpu').eval()
        self.lock = Lock()

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        torch = self.torch
        vectors = []
        with self.lock, torch.inference_mode():
            for offset in range(0, len(texts), batch_size):
                batch = self.tokenizer(texts[offset:offset + batch_size], max_length=512,
                                       padding=True, truncation=True, return_tensors='pt')
                output = self.model(**batch).last_hidden_state
                mask = batch['attention_mask']
                hidden = output.masked_fill(~mask[..., None].bool(), 0.)
                pooled = hidden.sum(dim=1) / mask.sum(dim=1)[..., None]
                vectors.append(torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy())
        return np.concatenate(vectors).astype(np.float32)
