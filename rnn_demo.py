import sys
from statistics import median
import numpy as np
from pybrain.structure import LinearLayer, SigmoidLayer, BiasUnit
from pybrain.structure import FullConnection
from pybrain.structure import RecurrentNetwork
from pybrain.datasets import SupervisedDataSet
from pybrain.supervised.trainers import BackpropTrainer
import data.ball_data as ball_data


BOX_SIZE = 10


def predict_ball(hidden_nodes, is_elman=True, training_data=5000, batch_size=-1, predict_count=64):
    b_size = training_data
    if batch_size > 0:
        if training_data < batch_size:
            raise Exception("training count have to be greater than training batch size")
        else:
            b_size = batch_size

    # build rnn
    n = construct_network(hidden_nodes, is_elman)

    # make training data
    initial_v = ball_data.gen_velocity(BOX_SIZE)
    data_set = None
    training_ds = SupervisedDataSet(4, 4)

    for b in range(training_data // b_size):
        d = ball_data.bounce_ball(b_size + 1, BOX_SIZE, None, initial_v=initial_v)
        data_set = d[:b_size] if data_set is None else np.vstack((data_set, d[:b_size]))

        d_normalized = __normalize(d)
        for i in range(b_size):
            # from current, predict next
            p_in = d_normalized[i].tolist()
            p_out = d_normalized[i + 1].tolist()
            training_ds.addSample(p_in, p_out)

    total_avg = np.average(data_set, axis=0)
    total_std = np.std(data_set, axis=0)
    del data_set  # release memory

    # training network
    trainer = BackpropTrainer(n, training_ds)
    err1 = trainer.train()
    del training_ds  # release memory

    # predict
    initial_p = ball_data.gen_position(BOX_SIZE)
    predict = None
    next_pv = np.hstack((initial_p, initial_v))

    n.reset()
    for i in range(predict_count):
        predict = next_pv if predict is None else np.vstack((predict, next_pv))

        p_normalized = (next_pv - total_avg) / total_std
        next_pv = n.activate(p_normalized.tolist())
        restored = np.array(next_pv) * total_std + total_avg
        next_pv = restored

    real = ball_data.bounce_ball(predict_count, BOX_SIZE, initial_p, initial_v)
    err_matrix = (predict - real) ** 2
    err_distance = np.sqrt(np.sum(err_matrix[:, 0:2], axis=1)).reshape((predict_count, 1))
    err_velocity = np.sum(np.sqrt(err_matrix[:, 2:4]), axis=1).reshape((predict_count, 1))
    err2 = np.hstack((err_distance, err_velocity))

    return predict, real, err1, err2


def construct_network(hidden_nodes, is_elman=True):
    n = RecurrentNetwork()
    n.addInputModule(LinearLayer(4, name="i"))
    n.addModule(BiasUnit("b"))
    n.addModule(SigmoidLayer(hidden_nodes, name="h"))
    n.addOutputModule(LinearLayer(4, name="o"))

    n.addConnection(FullConnection(n["i"], n["h"]))
    n.addConnection(FullConnection(n["b"], n["h"]))
    n.addConnection(FullConnection(n["b"], n["o"]))
    n.addConnection(FullConnection(n["h"], n["o"]))

    if is_elman:
        # Elman (hidden->hidden)
        n.addRecurrentConnection(FullConnection(n["h"], n["h"]))
    else:
        # Jordan (out->hidden)
        n.addRecurrentConnection(FullConnection(n["o"], n["h"]))

    n.sortModules()
    n.reset()

    return n


def __normalize(data):
    normalized = (data - np.average(data, axis=0)) / np.std(data, axis=0)
    return normalized


def describe_err(error, separator=","):
    params = np.hstack((np.mean(error, axis=0), np.std(error, axis=0)))
    return separator.join(["{0}".format(p) for p in params])


def measure_hidden_effect(min_hidden, max_hidden, is_elman=True, step=10, training_data=5000, trial_run=10):
    for h in range(min_hidden, max_hidden + step, step):
        training_e = []
        test_e = None

        for i in range(trial_run):
            p, r, e1, e2 = predict_ball(h, is_elman, training_data)
            training_e.append(e1)
            test_e = e2 if test_e is None else np.vstack((test_e, e2))

        print("{0}\t{1}\t{2}".format(h, median(training_e), describe_err(test_e, "\t")))


def measure_batch_effect(hidden_nodes, min_size, max_size, is_elman=True, step=100, training_data=20000, trial_run=10):
    for b in range(min_size, max_size + step, step):
        training_e = []
        test_e = None

        for i in range(trial_run):
            p, r, e1, e2 = predict_ball(hidden_nodes, is_elman, training_data, b)
            training_e.append(e1)
            test_e = e2 if test_e is None else np.vstack((test_e, e2))

        print("{0}\t{1}\t{2}".format(b, median(training_e), describe_err(test_e, "\t")))


def run(is_elman=True):
    nodes = 4
    p, r, e1, e2 = predict_ball(nodes, is_elman=is_elman, training_data=64000, batch_size=64)
    print("training error:{0}, test error:{1}".format(e1, describe_err(e2)))
    for x in p:
        print("{0}, {1}".format(x[0], x[1]))

    ball_data.show_animation([r], BOX_SIZE + 1)
    ball_data.show_animation([p], BOX_SIZE + 1)


def main(is_elman=True):
    # evaluate model by changing hidden layer
    # measure_batch_effect(4, 64, 2048, False, step=64)

    run(is_elman)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "E":
        main(True)
    else:
        main(False)
