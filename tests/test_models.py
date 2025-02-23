import pytest
from pytorch_lightning import Trainer
from pytorch_lightning.examples.new_project_templates.lightning_module_template import LightningTemplateModel
from pytorch_lightning.testing_models.lm_test_module import LightningTestModel
from argparse import Namespace
from test_tube import Experiment
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping
from pytorch_lightning.utils.debugging import MisconfigurationException
from pytorch_lightning.root_module import memory
from pytorch_lightning.models.trainer import reduce_distributed_output
import numpy as np
import warnings
import torch
import os
import shutil

SEED = 2334
torch.manual_seed(SEED)
np.random.seed(SEED)


# ------------------------------------------------------------------------
# TESTS
# ------------------------------------------------------------------------
def test_dp_output_reduce():

    # test identity when we have a single gpu
    out = torch.rand(3, 1)
    assert reduce_distributed_output(out, nb_gpus=1) is out

    # average when we have multiples
    assert reduce_distributed_output(out, nb_gpus=2) == out.mean()

    # when we have a dict of vals
    out = {
        'a': out,
        'b': {
            'c': out
        }
    }
    reduced = reduce_distributed_output(out, nb_gpus=3)
    assert reduced['a'] == out['a']
    assert reduced['b']['c'] == out['b']['c']


def test_amp_gpu_ddp_slurm_managed():
    """
    Make sure DDP + AMP work
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    os.environ['MASTER_PORT'] = str(np.random.randint(12000, 19000, 1)[0])

    hparams = get_hparams()
    model = LightningTestModel(hparams)

    trainer_options = dict(
        progress_bar=True,
        max_nb_epochs=1,
        gpus=[0],
        distributed_backend='ddp',
        use_amp=True
    )

    save_dir = init_save_dir()

    # exp file to get meta
    exp = get_exp(False)
    exp.argparse(hparams)
    exp.save()

    # exp file to get weights
    checkpoint = ModelCheckpoint(save_dir)

    # add these to the trainer options
    trainer_options['checkpoint_callback'] = checkpoint
    trainer_options['experiment'] = exp

    # fit model
    trainer = Trainer(**trainer_options)
    trainer.is_slurm_managing_tasks = True
    result = trainer.fit(model)

    # correct result and ok accuracy
    assert result == 1, 'amp + ddp model failed to complete'

    # test root model address
    assert trainer.resolve_root_node_address('abc') == 'abc'
    assert trainer.resolve_root_node_address('abc[23]') == 'abc23'
    assert trainer.resolve_root_node_address('abc[23-24]') == 'abc23'
    assert trainer.resolve_root_node_address('abc[23-24, 45-40, 40]') == 'abc23'

    # test model loading with a map_location
    map_location = 'cuda:1'
    pretrained_model = load_model(exp, save_dir, True, map_location)

    # test model preds
    run_prediction(model.test_dataloader, pretrained_model)

    if trainer.use_ddp:
        # on hpc this would work fine... but need to hack it for the purpose of the test
        trainer.model = pretrained_model
        trainer.optimizers = pretrained_model.configure_optimizers()

    # test HPC loading / saving
    trainer.hpc_save(save_dir, exp)
    trainer.hpc_load(save_dir, on_gpu=True)

    # test freeze on gpu
    model.freeze()
    model.unfreeze()

    clear_save_dir()


def test_early_stopping_cpu_model():
    """
    Test each of the trainer options
    :return:
    """

    stopping = EarlyStopping()
    trainer_options = dict(
        early_stop_callback=stopping,
        gradient_clip=1.0,
        overfit_pct=0.20,
        track_grad_norm=2,
        print_nan_grads=True,
        progress_bar=False,
        experiment=get_exp(),
        train_percent_check=0.1,
        val_percent_check=0.1
    )

    model, hparams = get_model()
    run_gpu_model_test(trainer_options, model, hparams, on_gpu=False)

    # test freeze on cpu
    model.freeze()
    model.unfreeze()


def test_cpu_model_with_amp():
    """
    Make sure model trains on CPU
    :return:
    """

    trainer_options = dict(
        progress_bar=False,
        experiment=get_exp(),
        max_nb_epochs=1,
        train_percent_check=0.4,
        val_percent_check=0.4,
        use_amp=True
    )

    model, hparams = get_model()

    with pytest.raises((MisconfigurationException, ModuleNotFoundError)):
        run_gpu_model_test(trainer_options, model, hparams, on_gpu=False)


def test_cpu_model():
    """
    Make sure model trains on CPU
    :return:
    """

    trainer_options = dict(
        progress_bar=False,
        experiment=get_exp(),
        max_nb_epochs=1,
        train_percent_check=0.4,
        val_percent_check=0.4
    )

    model, hparams = get_model()

    run_gpu_model_test(trainer_options, model, hparams, on_gpu=False)


def test_all_features_cpu_model():
    """
    Test each of the trainer options
    :return:
    """

    trainer_options = dict(
        gradient_clip=1.0,
        overfit_pct=0.20,
        track_grad_norm=2,
        print_nan_grads=True,
        progress_bar=False,
        experiment=get_exp(),
        max_nb_epochs=1,
        train_percent_check=0.4,
        val_percent_check=0.4
    )

    model, hparams = get_model()
    run_gpu_model_test(trainer_options, model, hparams, on_gpu=False)


def test_single_gpu_model():
    """
    Make sure single GPU works (DP mode)
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_single_gpu_model cannot run. Rerun on a GPU node to run this test')
        return
    model, hparams = get_model()

    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        train_percent_check=0.1,
        val_percent_check=0.1,
        gpus=[0]
    )

    run_gpu_model_test(trainer_options, model, hparams)


def test_multi_gpu_model_dp():
    """
    Make sure DP works
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_multi_gpu_model_dp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_multi_gpu_model_dp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return
    model, hparams = get_model()
    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        train_percent_check=0.1,
        val_percent_check=0.1,
        gpus='-1'
    )

    run_gpu_model_test(trainer_options, model, hparams)

    # test memory helper functions
    memory.get_gpu_memory_map()


def test_amp_gpu_dp():
    """
    Make sure DP + AMP work
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_dp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_dp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return
    model, hparams = get_model()
    trainer_options = dict(
        max_nb_epochs=1,
        gpus='0, 1',  # test init with gpu string
        distributed_backend='dp',
        use_amp=True
    )
    with pytest.raises(MisconfigurationException):
        run_gpu_model_test(trainer_options, model, hparams)


def test_multi_gpu_model_ddp():
    """
    Make sure DDP works
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_multi_gpu_model_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_multi_gpu_model_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    os.environ['MASTER_PORT'] = str(np.random.randint(12000, 19000, 1)[0])
    model, hparams = get_model()
    trainer_options = dict(
        progress_bar=False,
        max_nb_epochs=1,
        train_percent_check=0.4,
        val_percent_check=0.2,
        gpus=[0, 1],
        distributed_backend='ddp'
    )

    run_gpu_model_test(trainer_options, model, hparams)


def test_amp_gpu_ddp():
    """
    Make sure DDP + AMP work
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    os.environ['MASTER_PORT'] = str(np.random.randint(12000, 19000, 1)[0])

    hparams = get_hparams()
    model = LightningTestModel(hparams)

    trainer_options = dict(
        progress_bar=True,
        max_nb_epochs=1,
        gpus=[0, 1],
        distributed_backend='ddp',
        use_amp=True
    )

    run_gpu_model_test(trainer_options, model, hparams)


def test_ddp_sampler_error():
    """
    Make sure DDP + AMP work
    :return:
    """
    if not torch.cuda.is_available():
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a GPU node to run this test')
        return
    if not torch.cuda.device_count() > 1:
        warnings.warn('test_amp_gpu_ddp cannot run. Rerun on a node with 2+ GPUs to run this test')
        return

    os.environ['MASTER_PORT'] = str(np.random.randint(12000, 19000, 1)[0])

    hparams = get_hparams()
    model = LightningTestModel(hparams, force_remove_distributed_sampler=True)

    exp = get_exp(True)
    exp.save()

    trainer = Trainer(
        experiment=exp,
        progress_bar=False,
        max_nb_epochs=1,
        gpus=[0, 1],
        distributed_backend='ddp',
        use_amp=True
    )

    with pytest.raises(MisconfigurationException):
        trainer.get_dataloaders(model)

    clear_save_dir()


# ------------------------------------------------------------------------
# UTILS
# ------------------------------------------------------------------------
def run_gpu_model_test(trainer_options, model, hparams, on_gpu=True):
    save_dir = init_save_dir()

    # exp file to get meta
    exp = get_exp(False)
    exp.argparse(hparams)
    exp.save()

    # exp file to get weights
    checkpoint = ModelCheckpoint(save_dir)

    # add these to the trainer options
    trainer_options['checkpoint_callback'] = checkpoint
    trainer_options['experiment'] = exp

    # fit model
    trainer = Trainer(**trainer_options)
    result = trainer.fit(model)

    # correct result and ok accuracy
    assert result == 1, 'amp + ddp model failed to complete'

    # test model loading
    pretrained_model = load_model(exp, save_dir, on_gpu)

    # test model preds
    run_prediction(model.test_dataloader, pretrained_model)

    if trainer.use_ddp:
        # on hpc this would work fine... but need to hack it for the purpose of the test
        trainer.model = pretrained_model
        trainer.optimizers = pretrained_model.configure_optimizers()

    # test HPC loading / saving
    trainer.hpc_save(save_dir, exp)
    trainer.hpc_load(save_dir, on_gpu=on_gpu)

    clear_save_dir()


def get_hparams():
    root_dir = os.path.dirname(os.path.realpath(__file__))
    hparams = Namespace(**{'drop_prob': 0.2,
                           'batch_size': 32,
                           'in_features': 28*28,
                           'learning_rate': 0.001*8,
                           'optimizer_name': 'adam',
                           'data_root': os.path.join(root_dir, 'mnist'),
                           'out_features': 10,
                           'hidden_dim': 1000})
    return hparams


def get_model():
    # set up model with these hyperparams
    hparams = get_hparams()
    model = LightningTemplateModel(hparams)

    return model, hparams


def get_exp(debug=True):
    # set up exp object without actually saving logs
    root_dir = os.path.dirname(os.path.realpath(__file__))
    exp = Experiment(debug=debug, save_dir=root_dir, name='tests_tt_dir')
    return exp


def init_save_dir():
    root_dir = os.path.dirname(os.path.realpath(__file__))
    save_dir = os.path.join(root_dir, 'save_dir')

    if os.path.exists(save_dir):
        shutil.rmtree(save_dir)

    os.makedirs(save_dir, exist_ok=True)

    return save_dir


def clear_save_dir():
    root_dir = os.path.dirname(os.path.realpath(__file__))
    save_dir = os.path.join(root_dir, 'save_dir')
    if os.path.exists(save_dir):
        shutil.rmtree(save_dir)


def load_model(exp, save_dir, on_gpu, map_location=None):

    # load trained model
    tags_path = exp.get_data_path(exp.name, exp.version)
    tags_path = os.path.join(tags_path, 'meta_tags.csv')

    checkpoints = [x for x in os.listdir(save_dir) if '.ckpt' in x]
    weights_dir = os.path.join(save_dir, checkpoints[0])

    trained_model = LightningTemplateModel.load_from_metrics(weights_path=weights_dir,
                                                             tags_csv=tags_path,
                                                             on_gpu=on_gpu,
                                                             map_location=map_location)

    assert trained_model is not None, 'loading model failed'

    return trained_model


def run_prediction(dataloader, trained_model):
    # run prediction on 1 batch
    for batch in dataloader:
        break

    x, y = batch
    x = x.view(x.size(0), -1)

    y_hat = trained_model(x)

    # acc
    labels_hat = torch.argmax(y_hat, dim=1)
    val_acc = torch.sum(y == labels_hat).item() / (len(y) * 1.0)
    val_acc = torch.tensor(val_acc)
    val_acc = val_acc.item()

    print(val_acc)

    assert val_acc > 0.50, f'this model is expected to get > 0.50 in test set (it got {val_acc})'


def assert_ok_acc(trainer):
    # this model should get 0.80+ acc
    acc = trainer.tng_tqdm_dic['val_acc']
    assert acc > 0.50, f'model failed to get expected 0.50 validation accuracy. Got: {acc}'


if __name__ == '__main__':
    pytest.main([__file__])
