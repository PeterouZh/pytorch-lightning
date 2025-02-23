import os
from collections import OrderedDict
import torch.nn as nn
from torchvision.datasets import MNIST
import torchvision.transforms as transforms
import torch
import torch.nn.functional as F
from test_tube import HyperOptArgumentParser
from torch import optim
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler

from pytorch_lightning.root_module.root_module import LightningModule


class LightningTestModel(LightningModule):
    """
    Sample model to show how to define a template
    """

    def __init__(self, hparams, force_remove_distributed_sampler=False):
        """
        Pass in parsed HyperOptArgumentParser to the model
        :param hparams:
        """
        # init superclass
        super(LightningTestModel, self).__init__(hparams)

        self.batch_size = hparams.batch_size

        # if you specify an example input, the summary will show input/output for each layer
        self.example_input_array = torch.rand(5, 28 * 28)

        # remove to test warning for dist sampler
        self.force_remove_distributed_sampler = force_remove_distributed_sampler

        # build model
        self.__build_model()

    # ---------------------
    # MODEL SETUP
    # ---------------------
    def __build_model(self):
        """
        Layout model
        :return:
        """
        self.c_d1 = nn.Linear(in_features=self.hparams.in_features, out_features=self.hparams.hidden_dim)
        self.c_d1_bn = nn.BatchNorm1d(self.hparams.hidden_dim)
        self.c_d1_drop = nn.Dropout(self.hparams.drop_prob)

        self.c_d2 = nn.Linear(in_features=self.hparams.hidden_dim, out_features=self.hparams.out_features)

    # ---------------------
    # TRAINING
    # ---------------------
    def forward(self, x):
        """
        No special modification required for lightning, define as you normally would
        :param x:
        :return:
        """

        x = self.c_d1(x)
        x = torch.tanh(x)
        x = self.c_d1_bn(x)
        x = self.c_d1_drop(x)

        x = self.c_d2(x)
        logits = F.log_softmax(x, dim=1)

        return logits

    def loss(self, labels, logits):
        nll = F.nll_loss(logits, labels)
        return nll

    def training_step(self, data_batch, batch_i):
        """
        Lightning calls this inside the training loop
        :param data_batch:
        :return:
        """
        # forward pass
        x, y = data_batch
        x = x.view(x.size(0), -1)

        y_hat = self.forward(x)

        # calculate loss
        loss_val = self.loss(y, y_hat)

        # in DP mode (default) make sure if result is scalar, there's another dim in the beginning
        if self.trainer.use_dp:
            loss_val = loss_val.unsqueeze(0)

        output = OrderedDict({
            'loss': loss_val
        })

        # can also return just a scalar instead of a dict (return loss_val)
        return output

    def validation_step(self, data_batch, batch_i):
        """
        Lightning calls this inside the validation loop
        :param data_batch:
        :return:
        """
        x, y = data_batch
        x = x.view(x.size(0), -1)
        y_hat = self.forward(x)

        loss_val = self.loss(y, y_hat)

        # acc
        labels_hat = torch.argmax(y_hat, dim=1)
        val_acc = torch.sum(y == labels_hat).item() / (len(y) * 1.0)
        val_acc = torch.tensor(val_acc)

        if self.on_gpu:
            val_acc = val_acc.cuda(loss_val.device.index)

        # in DP mode (default) make sure if result is scalar, there's another dim in the beginning
        if self.trainer.use_dp:
            loss_val = loss_val.unsqueeze(0)
            val_acc = val_acc.unsqueeze(0)

        # alternate possible outputs to test
        if self.trainer.batch_nb % 1 == 0:
            output = OrderedDict({
                'val_loss': loss_val,
                'val_acc': val_acc,
            })
            return output
        if self.trainer.batch_nb % 2 == 0:
            return val_acc

        if self.trainer.batch_nb % 3 == 0:
            output = OrderedDict({
                'val_loss': loss_val,
                'val_acc': val_acc,
                'test_dic': {'val_loss_a': loss_val}
            })
            return output

    def validation_end(self, outputs):
        """
        Called at the end of validation to aggregate outputs
        :param outputs: list of individual outputs of each validation step
        :return:
        """
        # if returned a scalar from validation_step, outputs is a list of tensor scalars
        # we return just the average in this case (if we want)
        # return torch.stack(outputs).mean()

        val_loss_mean = 0
        val_acc_mean = 0
        for output in outputs:
            val_loss_mean += output['val_loss']
            val_acc_mean += output['val_acc']

        val_loss_mean /= len(outputs)
        val_acc_mean /= len(outputs)

        tqdm_dic = {'val_loss': val_loss_mean.item(), 'val_acc': val_acc_mean.item()}
        return tqdm_dic

    def on_tng_metrics(self, logs):
        logs['some_tensor_to_test'] = torch.rand(1)

    # ---------------------
    # MODEL SAVING
    # ---------------------
    def get_save_dict(self):
        checkpoint = {'state_dict': self.state_dict()}
        return checkpoint

    def load_model_specific(self, checkpoint):
        self.load_state_dict(checkpoint['state_dict'])
        pass

    # ---------------------
    # TRAINING SETUP
    # ---------------------
    def configure_optimizers(self):
        """
        return whatever optimizers we want here
        :return: list of optimizers
        """
        optimizer = optim.Adam(self.parameters(), lr=self.hparams.learning_rate)
        return [optimizer]

    def __dataloader(self, train):
        # init data generators
        transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (1.0,))])
        dataset = MNIST(root=self.hparams.data_root, train=train, transform=transform, download=True)

        # when using multi-node we need to add the datasampler
        train_sampler = None
        batch_size = self.hparams.batch_size

        try:
            if self.on_gpu and not self.force_remove_distributed_sampler:
                train_sampler = DistributedSampler(dataset, rank=self.trainer.proc_rank)
                batch_size = batch_size // self.trainer.world_size  # scale batch size
        except Exception as e:
            pass

        should_shuffle = train_sampler is None
        loader = DataLoader(
            dataset=dataset,
            batch_size=batch_size,
            shuffle=should_shuffle,
            sampler=train_sampler
        )

        return loader

    @property
    def tng_dataloader(self):
        if self._tng_dataloader is None:
            try:
                self._tng_dataloader = self.__dataloader(train=True)
            except Exception as e:
                print(e)
                raise e
        return self._tng_dataloader

    @property
    def val_dataloader(self):
        if self._val_dataloader is None:
            try:
                self._val_dataloader = self.__dataloader(train=False)
            except Exception as e:
                print(e)
                raise e
        return self._val_dataloader

    @property
    def test_dataloader(self):
        if self._test_dataloader is None:
            try:
                self._test_dataloader = self.__dataloader(train=False)
            except Exception as e:
                print(e)
                raise e
        return self._test_dataloader

    @staticmethod
    def add_model_specific_args(parent_parser, root_dir):
        """
        Parameters you define here will be available to your model through self.hparams
        :param parent_parser:
        :param root_dir:
        :return:
        """
        parser = HyperOptArgumentParser(strategy=parent_parser.strategy, parents=[parent_parser])

        # param overwrites
        # parser.set_defaults(gradient_clip=5.0)

        # network params
        parser.opt_list('--drop_prob', default=0.2, options=[0.2, 0.5], type=float, tunable=False)
        parser.add_argument('--in_features', default=28*28, type=int)
        parser.add_argument('--out_features', default=10, type=int)
        parser.add_argument('--hidden_dim', default=50000, type=int) # use 500 for CPU, 50000 for GPU to see speed difference

        # data
        parser.add_argument('--data_root', default=os.path.join(root_dir, 'mnist'), type=str)

        # training params (opt)
        parser.opt_list('--learning_rate', default=0.001*8, type=float, options=[0.0001, 0.0005, 0.001, 0.005],
                        tunable=False)
        parser.opt_list('--optimizer_name', default='adam', type=str, options=['adam'], tunable=False)

        # if using 2 nodes with 4 gpus each the batch size here (256) will be 256 / (2*8) = 16 per gpu
        parser.opt_list('--batch_size', default=256*8, type=int, options=[32, 64, 128, 256], tunable=False,
                        help='batch size will be divided over all the gpus being used across all nodes')
        return parser
