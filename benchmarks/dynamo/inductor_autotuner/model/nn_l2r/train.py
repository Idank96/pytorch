import argparse
import os
import pickle

import numpy as np
import torch
import tqdm
from torch._inductor.autotuner.model import AutotunerModel, ModelType

parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", type=str, default="./")
parser.add_argument("--output_dir", type=str, default="./")
parser.add_argument("--epoch", type=int, default=1000)
parser.add_argument("--lr", type=float, default=1e-4)
parser.add_argument("--batch_size", type=int, default=4096)
parser.add_argument("--full_train", action="store_true", default=False)


np.random.seed(0)
np.set_printoptions(threshold=np.inf, suppress=True)
np.set_printoptions(edgeitems=30, linewidth=100000)


def main(args):
    data_dir = args.data_dir
    output_dir = args.output_dir
    n_epoch = args.epoch
    lr = args.lr
    batch_size = args.batch_size
    full_train = args.full_train

    def load(file_name):
        file_name = os.path.join(data_dir, file_name)
        print("Loading " + file_name)
        with open(file_name, "rb") as f:
            return pickle.load(f)

    X_train = load("X_pairwise_train.pkl")
    y_train = load("y_pairwise_train.pkl")

    X_test = load("X_pairwise_test.pkl")
    y_test = load("y_pairwise_test.pkl")

    y_train = np.array(y_train)
    y_test = np.array(y_test)

    y_train[y_train > 1] = 1
    y_test[y_test > 1] = 1

    autotuner = AutotunerModel(ModelType.NN_PAIRWISE)

    if full_train:
        X = (
            tuple(
                torch.concatenate([X_train[0][i], X_test[0][i]])
                for i in range(len(X_train[0]))
            ),
            tuple(
                torch.concatenate([X_train[1][i], X_test[1][i]])
                for i in range(len(X_train[1]))
            ),
        )
        y = np.concatenate([y_train, y_test])
    else:
        X = X_train
        y = y_train

    def get_loss(X_loss, y_loss):
        test_batch_size = 8192 * 4
        loss_sum = 0
        acc_sum = 0
        autotuner.model.eval()

        with torch.no_grad():
            for i in range(0, y_loss.shape[0], test_batch_size):
                X_loss_batch = (
                    tuple(
                        X_group[i : i + test_batch_size].to("cuda")
                        for X_group in X_loss[0]
                    ),
                    tuple(
                        X_group[i : i + test_batch_size].to("cuda")
                        for X_group in X_loss[1]
                    ),
                )
                X_loss_batch = tuple(
                    torch.cat([X_loss_batch[0][i], X_loss_batch[1][i]], dim=0)
                    for i in range(len(X_loss_batch[0]))
                )
                y_loss_batch = torch.from_numpy(y_loss[i : i + test_batch_size]).to(
                    "cuda"
                )
                y_pred = autotuner.model.forward_(X_loss_batch).squeeze()
                scores = (
                    y_pred[: y_loss_batch.shape[0]] - y_pred[y_loss_batch.shape[0] :]
                )
                loss_sum += (
                    torch.log(1 + torch.exp(-scores)) * (y_loss_batch**2)
                ).sum()
                acc_sum += (scores > 0).sum()
            torch.cuda.empty_cache()

        return loss_sum / y_loss.shape[0], acc_sum / y_loss.shape[0]

    autotuner.model.to("cuda")
    optimizer = torch.optim.Adam(autotuner.model.parameters(), lr=lr)
    print("X")
    print("left")
    for X_group in X[0]:
        print(X_group.shape)
    print("right")
    for X_group in X[1]:
        print(X_group.shape)
    print(y.shape)

    for epoch in range(n_epoch):
        permutation = np.random.permutation(y.shape[0])
        X_epoch = (
            tuple(X_group[permutation] for X_group in X[0]),
            tuple(X_group[permutation] for X_group in X[1]),
        )
        y_epoch = y[permutation]

        train_loss_sum = 0
        train_acc_sum = 0
        for i in tqdm.tqdm(range(0, y_epoch.shape[0], batch_size)):
            optimizer.zero_grad()
            X_batch = (
                tuple(X_group[i : i + batch_size].to("cuda") for X_group in X_epoch[0]),
                tuple(X_group[i : i + batch_size].to("cuda") for X_group in X_epoch[1]),
            )
            X_batch = tuple(
                torch.cat([X_batch[0][i], X_batch[1][i]], dim=0)
                for i in range(len(X_batch[0]))
            )
            y_batch = torch.from_numpy(y_epoch[i : i + batch_size]).to("cuda")
            y_pred = autotuner.model.forward_(X_batch).squeeze()
            scores = y_pred[: y_batch.shape[0]] - y_pred[y_batch.shape[0] :]
            loss = (torch.log(1 + torch.exp(-scores)) * (y_batch**2)).mean()
            train_loss_sum += loss.item() * y_batch.shape[0]
            train_acc_sum += (scores > 0).sum()
            loss.backward()
            optimizer.step()

        print(
            f"Train: epoch={epoch} loss = {train_loss_sum / y_epoch.shape[0]}, acc = {train_acc_sum / y_epoch.shape[0]}",
            end=" ||| ",
        )
        cur_loss, acc = get_loss(X_test, y_test)
        print(f"Test: epoch={epoch} loss = {cur_loss.item()}, acc = {acc.item()}")

        # dump model
        with open(
            os.path.join(
                output_dir,
                f"nn_l2r_{full_train}_{epoch}_{cur_loss.item()}_{acc.item()}.pkl",
            ),
            "wb",
        ) as f:
            pickle.dump(autotuner, f)


if __name__ == "__main__":
    args = parser.parse_args()
    main(args)
