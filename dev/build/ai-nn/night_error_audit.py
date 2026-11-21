"""Read-only prediction diagnostics on the overnight validation cache, never test."""
import numpy as np
import torch
from overnight_common import B, guard, read, write
from overnight_train import batches, initialize, load_cache, OFFSETS

guard()
torch.set_num_threads(1)
_, rows = load_cache(B / 'data/validation.npz')
with np.load(B / 'data/train.npz', allow_pickle=False) as cache:
    plant = cache['g'][:, 0] > .5
    train_counts = dict(
        cache_rows=len(plant),
        plant_economy=np.bincount(cache['y'][plant, 0], minlength=12).tolist(),
        zombie_graves=np.bincount(cache['y'][~plant, 2], minlength=11).tolist())
result = dict(scope='Validation head predictions before runtime guards; sealed test not read.',
              training_cache_counts_before_overlap_filter=train_counts, models={})
for folder in sorted((B / 'models').glob('initial-*')):
    if not (folder / 'report.json').exists():
        continue
    doc = read(folder / 'model.json')
    transition = bool(doc.get('mode_transition'))
    model = initialize(doc, doc.get('mode_hidden', 0), transition).eval()
    confusion = [np.zeros((OFFSETS[h+1]-OFFSETS[h],)*2, dtype=np.int64) for h in range(3)]
    mode = dict(teacher_switch=0, correct_switch=0, false_switch=0, missed_switch=0)
    rare = []
    with torch.no_grad():
        for x, side, target, weights in batches(rows):
            logits = model(*x)
            for h in range(3):
                mask = side if h < 2 else ~side
                pred = logits[:, OFFSETS[h]:OFFSETS[h+1]].argmax(1)
                if h == 1 and transition:
                    pred = pred ^ (x[0][:, 11] > .5).long()
                np.add.at(confusion[h], (target[mask, h].numpy(), pred[mask].numpy()), 1)
                if h == 1:
                    previous = (x[0][:, 11] > .5).long()
                    changed = mask & (target[:, h] != previous)
                    proposed = mask & (pred != previous)
                    mode['teacher_switch'] += int(changed.sum())
                    mode['correct_switch'] += int((changed & proposed).sum())
                    mode['false_switch'] += int((~changed & proposed).sum())
                    mode['missed_switch'] += int((changed & ~proposed).sum())
                if h == 0:
                    for i in (mask & (target[:, h] == 11)).nonzero().flatten().tolist():
                        rare.append(dict(target=11, prediction=int(pred[i]), global_features=x[0][i].tolist()))
    result['models'][folder.name] = dict(confusion_true_rows_predicted_columns=[m.tolist() for m in confusion],
                                       mode=mode, goal_11=rare)
write(B / 'validation-error-audit.json', result)
guard()
print({k: v['mode'] for k, v in result['models'].items()})
