"""Fine-tune a ViT dish classifier on ArabFood-N (needs a GPU or Apple Silicon).

    pip install torch torchvision timm
    python scripts/train_classifier.py --epochs 15 --model vit_base_patch16_224

Expects data/annotations.csv with columns image_file, dish_id, session_id, split.
Split is by cooking session (never by image) so the same plate is never in train and test.
"""
import argparse
import csv
from pathlib import Path

import timm
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[1]


class FoodSet(Dataset):
    def __init__(self, rows, classes, tf):
        self.rows, self.idx, self.tf = rows, {c: i for i, c in enumerate(classes)}, tf

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(ROOT / "data" / "images" / r["image_file"]).convert("RGB")
        return self.tf(img), self.idx[r["dish_id"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="vit_base_patch16_224")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    rows = list(csv.DictReader(open(ROOT / "data" / "annotations.csv", encoding="utf-8")))
    classes = sorted({r["dish_id"] for r in rows})
    dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    model = timm.create_model(a.model, pretrained=True, num_classes=len(classes)).to(dev)
    cfg = timm.data.resolve_data_config({}, model=model)
    tf_train = timm.data.create_transform(**cfg, is_training=True)
    tf_eval = timm.data.create_transform(**cfg)
    tr = DataLoader(FoodSet([r for r in rows if r["split"] == "train"], classes, tf_train), a.bs, shuffle=True)
    te = DataLoader(FoodSet([r for r in rows if r["split"] == "test"], classes, tf_eval), a.bs)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.05)
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=0.1)
    for ep in range(a.epochs):
        model.train()
        for x, y in tr:
            opt.zero_grad()
            loss = loss_fn(model(x.to(dev)), y.to(dev))
            loss.backward()
            opt.step()
        model.eval()
        top1 = top3 = n = 0
        with torch.no_grad():
            for x, y in te:
                out = model(x.to(dev)).topk(3, dim=1).indices.cpu()
                top1 += (out[:, 0] == y).sum().item()
                top3 += (out == y[:, None]).any(1).sum().item()
                n += len(y)
        print(f"epoch {ep + 1}: loss {loss.item():.3f}  top1 {top1 / n:.3f}  top3 {top3 / n:.3f}")
    out = ROOT / "results" / f"{a.model}_seed{a.seed}.pt"
    out.parent.mkdir(exist_ok=True)
    torch.save({"state": model.state_dict(), "classes": classes}, out)
    print("saved", out)


if __name__ == "__main__":
    main()
