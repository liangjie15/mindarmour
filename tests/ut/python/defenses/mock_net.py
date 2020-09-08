# Copyright 2019 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
mocked model for UT of defense algorithms.
"""
import numpy as np

from mindspore import nn
from mindspore import Tensor
from mindspore.nn import WithLossCell, TrainOneStepCell
from mindspore.nn.optim.momentum import Momentum
from mindspore import context
from mindspore.common.initializer import TruncatedNormal

from mindarmour.adv_robustness.attacks import FastGradientSignMethod


def conv(in_channels, out_channels, kernel_size, stride=1, padding=0):
    weight = weight_variable()
    return nn.Conv2d(in_channels, out_channels,
                     kernel_size=kernel_size, stride=stride, padding=padding,
                     weight_init=weight, has_bias=False, pad_mode="valid")


def fc_with_initialize(input_channels, out_channels):
    weight = weight_variable()
    bias = weight_variable()
    return nn.Dense(input_channels, out_channels, weight, bias)


def weight_variable():
    return TruncatedNormal(0.02)


class Net(nn.Cell):
    """
    Lenet network
    """
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = conv(1, 6, 5)
        self.conv2 = conv(6, 16, 5)
        self.fc1 = fc_with_initialize(16*5*5, 120)
        self.fc2 = fc_with_initialize(120, 84)
        self.fc3 = fc_with_initialize(84, 10)
        self.relu = nn.ReLU()
        self.max_pool2d = nn.MaxPool2d(kernel_size=2, stride=2)
        self.flatten = nn.Flatten()

    def construct(self, x):
        x = self.conv1(x)
        x = self.relu(x)
        x = self.max_pool2d(x)
        x = self.conv2(x)
        x = self.relu(x)
        x = self.max_pool2d(x)
        x = self.flatten(x)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        x = self.relu(x)
        x = self.fc3(x)
        return x


if __name__ == '__main__':
    num_classes = 10
    batch_size = 32

    sparse = False
    context.set_context(mode=context.GRAPH_MODE)
    context.set_context(device_target='Ascend')

    # create test data
    inputs_np = np.random.rand(batch_size, 1, 32, 32).astype(np.float32)
    labels_np = np.random.randint(num_classes, size=batch_size).astype(np.int32)
    if not sparse:
        labels_np = np.eye(num_classes)[labels_np].astype(np.float32)

    net = Net()

    # test fgsm
    attack = FastGradientSignMethod(net, eps=0.3)
    attack.generate(inputs_np, labels_np)

    # test train ops
    loss_fn = nn.SoftmaxCrossEntropyWithLogits(sparse=sparse)
    optimizer = Momentum(filter(lambda x: x.requires_grad, net.get_parameters()),
                         0.01, 0.9)
    loss_net = WithLossCell(net, loss_fn)
    train_net = TrainOneStepCell(loss_net, optimizer)
    train_net.set_train()

    train_net(Tensor(inputs_np), Tensor(labels_np))
